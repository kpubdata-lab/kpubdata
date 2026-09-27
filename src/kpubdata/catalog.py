"""Catalog — dataset discovery, search and resolution."""

from __future__ import annotations

import builtins
import logging
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from kpubdata.core.models import DatasetRef
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import DatasetNotFoundError
from kpubdata.registry import ProviderRegistry

logger = logging.getLogger("kpubdata.catalog")

# Minimum relevance score (0.0–1.0) for a dataset to be included in search
# results.
_DEFAULT_SCORE_THRESHOLD = 0.5

# Token-overlap score band — kept strictly below the exact-substring 1.0 so
# that an exact substring match always keeps its ranking priority.
_TOKEN_OVERLAP_FLOOR = 0.7
_TOKEN_OVERLAP_CEIL = 0.95

# Unicode word tokens (letters, digits, underscore). Identifier-shaped tokens
# like ``village_fcst`` stay a single token, which matches how dataset_key
# strings are written in provider catalogues.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _normalize(text: str) -> str:
    """Normalize a string for search comparison: NFC, strip, then casefold."""
    return unicodedata.normalize("NFC", text).strip().casefold()


def _tokenize(text: str) -> frozenset[str]:
    """Decompose *text* into a deterministic set of normalized word tokens."""
    if not text:
        return frozenset()
    return frozenset(_TOKEN_RE.findall(_normalize(text)))


@dataclass(slots=True, frozen=True)
class _IndexedItem:
    """Pre-computed search payload for a single dataset.

    Holds a :class:`DatasetRef` together with its normalized field strings
    and deterministic token set, so :class:`Catalog.search` can score each
    item without redoing normalization work on every call.
    """

    dataset: DatasetRef
    fields: tuple[str, ...]
    tokens: frozenset[str]


def _build_index(datasets: builtins.list[DatasetRef]) -> builtins.list[_IndexedItem]:
    """Build the in-memory search index for *datasets*.

    Each item exposes the normalized field strings (name, description,
    tags, id, dataset_key, provider) and the union of word tokens extracted
    from those fields. Index construction is O(n) in the candidate-set size
    and runs once per search call.
    """
    index: builtins.list[_IndexedItem] = []
    for dataset in datasets:
        field_sources: builtins.list[str] = [
            dataset.name,
            dataset.id,
            dataset.dataset_key,
            dataset.provider,
        ]
        if dataset.description:
            field_sources.append(dataset.description)
        field_sources.extend(dataset.tags)

        normalized_fields: builtins.list[str] = []
        tokens: set[str] = set()
        for source in field_sources:
            normalized = _normalize(source)
            normalized_fields.append(normalized)
            tokens.update(_TOKEN_RE.findall(normalized))

        index.append(
            _IndexedItem(
                dataset=dataset,
                fields=tuple(normalized_fields),
                tokens=frozenset(tokens),
            )
        )
    return index


def _score_indexed(
    needle: str,
    needle_tokens: frozenset[str],
    item: _IndexedItem,
) -> float:
    """Score *item* using a pre-normalized query and its token set.

    The score tiers, in priority order:

    1. An **exact substring** match in any indexed field → ``1.0``.
    2. **Token overlap** = matched query tokens / total query tokens. The
       value is mapped onto the ``[_TOKEN_OVERLAP_FLOOR,
       _TOKEN_OVERLAP_CEIL]`` band so token evidence never outranks a
       substring match.
    3. A **fuzzy correction** using ``SequenceMatcher`` ratios across the
       fields.

    When tier 1 does not match, the final score is ``max(tier 2, tier 3)``.
    The intent is to keep the existing recall (fuzzy results are not
    dropped) while letting token evidence pull borderline results above the
    threshold more reliably.
    """
    if not needle:
        return 1.0

    for text in item.fields:
        if needle in text:
            return 1.0

    overlap_score = 0.0
    if needle_tokens:
        matched = len(needle_tokens & item.tokens)
        if matched:
            ratio = matched / len(needle_tokens)
            overlap_score = (
                _TOKEN_OVERLAP_FLOOR + (_TOKEN_OVERLAP_CEIL - _TOKEN_OVERLAP_FLOOR) * ratio
            )

    fuzzy_score = 0.0
    for text in item.fields:
        candidate = SequenceMatcher(None, needle, text).ratio()
        if candidate > fuzzy_score:
            fuzzy_score = candidate

    return max(overlap_score, fuzzy_score)


def _score_dataset(needle: str, dataset: DatasetRef) -> float:
    """Score a single dataset against *needle* (public internal helper).

    Kept for callers that want to score one dataset without building the
    full index. Internally it creates a one-off index item so the behavior
    matches :class:`Catalog.search`.
    """
    needle_normalized = _normalize(needle)
    if not needle_normalized:
        return 1.0
    needle_tokens = frozenset(_TOKEN_RE.findall(needle_normalized))
    index = _build_index([dataset])
    return _score_indexed(needle_normalized, needle_tokens, index[0])


class Catalog:
    """Provides dataset discovery across the registered providers."""

    _registry: ProviderRegistry

    def __init__(self, registry: ProviderRegistry) -> None:
        """Initialize a catalog bound to a provider registry."""

        self._registry = registry
        # Single-entry search-index cache (#279): the key is (provider,
        # dataset-id tuple); any change to the catalog composition changes
        # the key and triggers a rebuild automatically.
        self._index_cache_key: tuple[str | None, tuple[str, ...]] | None = None
        self._index_cache: builtins.list[_IndexedItem] = []

    def _cached_index(
        self, provider: str | None, candidates: builtins.list[DatasetRef]
    ) -> builtins.list[_IndexedItem]:
        """Reuse the search index (#279).

        When the candidate id list is unchanged, the index built by a
        previous call (including NFC normalization and tokenization) is
        reused as-is — the catalog is deterministic within a process (it is
        catalogue.json based), so the id set is sufficient to identify the
        index content. A change in registry/provider composition changes
        the key and forces an immediate rebuild.
        """
        key = (provider, tuple(dataset.id for dataset in candidates))
        if key != self._index_cache_key:
            self._index_cache = _build_index(candidates)
            self._index_cache_key = key
        return self._index_cache

    def list(self, *, provider: str | None = None) -> builtins.list[DatasetRef]:
        """Return the discoverable datasets, optionally filtered by provider.

        Raises:
            ProviderNotRegisteredError: ``provider`` was given but is unknown.
        """

        logger.debug("Catalog list", extra={"provider_filter": provider})
        if provider is not None:
            adapter = self._get_adapter(provider)
            provider_datasets = adapter.list_datasets()
            logger.debug(
                "Catalog list result",
                extra={"provider": provider, "count": len(provider_datasets)},
            )
            return provider_datasets

        datasets: builtins.list[DatasetRef] = []
        for provider_name in self._registry:
            adapter = self._get_adapter(provider_name)
            datasets.extend(adapter.list_datasets())
        logger.debug(
            "Catalog list result",
            extra={"provider": None, "count": len(datasets)},
        )
        return datasets

    def search(
        self,
        text: str,
        *,
        provider: str | None = None,
        threshold: float = _DEFAULT_SCORE_THRESHOLD,
    ) -> builtins.list[DatasetRef]:
        """Search datasets by fuzzy-matching name, description, tags and id.

        Results are returned in descending relevance order. Only datasets
        whose score meets *threshold* (0.0–1.0) are included.

        Raises:
            ProviderNotRegisteredError: ``provider`` was given but is unknown.
        """

        logger.debug(
            "Catalog search",
            extra={"text": text, "provider_filter": provider, "threshold": threshold},
        )
        candidates = self.list(provider=provider)
        index = self._cached_index(provider, candidates)

        needle_normalized = _normalize(text)
        needle_tokens = frozenset(_TOKEN_RE.findall(needle_normalized))

        scored: builtins.list[tuple[float, DatasetRef]] = []
        for item in index:
            score = _score_indexed(needle_normalized, needle_tokens, item)
            if score >= threshold:
                scored.append((score, item.dataset))

        # Sort by descending score, then by id for a stable order
        scored.sort(key=lambda pair: (-pair[0], pair[1].id))
        results = [dataset for _, dataset in scored]

        logger.debug(
            "Catalog search result",
            extra={
                "provider": provider,
                "text": text,
                "candidates": len(candidates),
                "count": len(results),
            },
        )
        return results

    def resolve(self, dataset_id: str) -> tuple[ProviderAdapter, DatasetRef]:
        """Resolve ``provider.dataset_key`` into an adapter and dataset ref.

        Raises:
            DatasetNotFoundError: The dataset id is malformed or not found.
            ProviderNotRegisteredError: The provider is not registered.
        """

        provider_name, dataset_key = self._split_dataset_id(dataset_id)
        logger.debug(
            "Catalog resolve",
            extra={
                "dataset_id": dataset_id,
                "provider": provider_name,
                "dataset_key": dataset_key,
            },
        )
        adapter = self._get_adapter(provider_name)

        try:
            return adapter, adapter.get_dataset(dataset_key)
        except DatasetNotFoundError:
            logger.debug(
                "Catalog resolve failed: dataset not found",
                extra={"dataset_id": dataset_id, "provider": provider_name},
            )
            raise
        except Exception as exc:
            logger.debug(
                "Catalog resolve failed: adapter raised",
                extra={
                    "dataset_id": dataset_id,
                    "provider": provider_name,
                    "exception_type": type(exc).__name__,
                },
            )
            raise DatasetNotFoundError(
                f"Dataset not found: {dataset_id}",
                provider=provider_name,
                dataset_id=dataset_id,
            ) from exc

    def _get_adapter(self, provider: str) -> ProviderAdapter:
        """Fetch a provider adapter from the registry or raise the canonical exception."""

        return self._registry.get(provider)

    @staticmethod
    def _split_dataset_id(dataset_id: str) -> tuple[str, str]:
        """Split a canonical dataset id into ``(provider, dataset_key)``."""

        parts = dataset_id.split(".", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise DatasetNotFoundError(
                f"Invalid dataset id format: {dataset_id}", dataset_id=dataset_id
            )
        return parts[0], parts[1]


__all__ = ["Catalog", "_score_dataset", "_tokenize"]
