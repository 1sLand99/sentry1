import {type ReactNode, useMemo} from 'react';
import type Fuse from 'fuse.js';

import {useSearchQueryBuilder} from 'sentry/components/searchQueryBuilder/context';
import type {
  KeySectionItem,
  RawSearchFilterHasValueItem,
  SearchKeyItem,
} from 'sentry/components/searchQueryBuilder/tokens/filterKeyListBox/types';
import {
  createAskSeerConsentItem,
  createAskSeerItem,
  createFilterValueItem,
  createItem,
  createRawSearchFilterHasValueItem,
  createRawSearchFilterIsValueItem,
  createRawSearchItem,
} from 'sentry/components/searchQueryBuilder/tokens/filterKeyListBox/utils';
import type {FieldDefinitionGetter} from 'sentry/components/searchQueryBuilder/types';
import type {Tag} from 'sentry/types/group';
import {defined} from 'sentry/utils';
import {FieldKey} from 'sentry/utils/fields';
import {useFuzzySearch} from 'sentry/utils/fuzzySearch';
import useOrganization from 'sentry/utils/useOrganization';

type FilterKeySearchItem = {
  description: string;
  item: Tag;
  keywords: string[];
  type: 'value' | 'key';
  key?: string;
  value?: string;
};

const FUZZY_SEARCH_OPTIONS: Fuse.IFuseOptions<FilterKeySearchItem> = {
  keys: [
    {name: 'key', weight: 10},
    {name: 'value', weight: 7},
    {name: 'keywords', weight: 2},
    {name: 'description', weight: 1},
  ],
  threshold: 0.2,
  includeMatches: false,
  minMatchCharLength: 1,
  includeScore: true,
  distance: 1000,
};

function isQuoted(inputValue: string) {
  return inputValue.startsWith('"') && inputValue.endsWith('"');
}

// Adds static filter values to the searchable items so that they can be
// suggested if they appear high in the search results.
function getFilterSearchValues(
  keys: Tag[],
  {getFieldDefinition}: {getFieldDefinition: FieldDefinitionGetter}
): FilterKeySearchItem[] {
  return keys.reduce<FilterKeySearchItem[]>((acc, key) => {
    const fieldDef = getFieldDefinition(key.key);
    const values = key.values ?? fieldDef?.values ?? [];

    const addItem = (value: string, description: ReactNode = '') => {
      acc.push({
        value,
        description: typeof description === 'string' ? description : '',
        keywords: [],
        type: 'value',
        item: key,
      });
    };

    for (const value of values) {
      if (typeof value === 'string') {
        addItem(value);
      } else {
        if (value.children.length) {
          for (const child of value.children) {
            if (child.value) {
              addItem(child.value, child.desc ?? child.documentation);
            }
          }
        } else {
          if (value.value) {
            addItem(value.value, value.desc ?? value.documentation);
          }
        }
      }
    }

    return acc;
  }, []);
}

// Returns a section of suggested filter values.
// This will suggest a maximum of 3 options and will display them
// at the top only if the score is better than any of the keys.
function getValueSuggestionsFromSearchResult(
  results: Array<Fuse.FuseResult<FilterKeySearchItem>>
) {
  const suggestions = results
    .filter(result => result.item.type === 'value')
    // Sort HAS suggestions below others because they are less valuable
    .sort((a, b) =>
      a.item.item.key === FieldKey.HAS && b.item.item.key !== FieldKey.HAS ? 1 : -1
    )
    .map(result => createFilterValueItem(result.item.item.key, result.item.value ?? ''))
    .slice(0, 3);

  const suggestedFiltersSection: KeySectionItem = {
    key: 'suggested-filters',
    value: 'suggested-filters',
    label: '',
    options: suggestions,
    type: 'section',
  };

  const topItemIsValueSuggestion = results[0]?.item?.type === 'value';
  const hasValueSuggestions = suggestions.length > 0;

  return {
    shouldShowAtTop: topItemIsValueSuggestion,
    suggestedFiltersSection: hasValueSuggestions ? suggestedFiltersSection : null,
  };
}

export function useSortedFilterKeyItems({
  inputValue,
  filterValue,
  includeSuggestions,
}: {
  filterValue: string;
  includeSuggestions: boolean;
  inputValue: string;
}): SearchKeyItem[] {
  const {
    filterKeys,
    getFieldDefinition,
    filterKeySections,
    disallowFreeText,
    replaceRawSearchKeys,
    matchKeySuggestions,
    enableAISearch,
    gaveSeerConsent,
  } = useSearchQueryBuilder();
  const organization = useOrganization();
  const hasWildcardSearch = organization.features.includes(
    'search-query-builder-wildcard-operators'
  );

  const flatKeys = useMemo(() => Object.values(filterKeys), [filterKeys]);

  const searchableItems = useMemo<FilterKeySearchItem[]>(() => {
    const searchKeyItems: FilterKeySearchItem[] = flatKeys.map(key => {
      const fieldDef = getFieldDefinition(key.key);

      return {
        key: key.key,
        description: fieldDef?.desc ?? '',
        keywords: fieldDef?.keywords ?? [],
        item: key,
        type: 'key',
      };
    });

    if (includeSuggestions) {
      return [
        ...searchKeyItems,
        ...getFilterSearchValues(flatKeys, {getFieldDefinition}),
      ];
    }

    return searchKeyItems;
  }, [flatKeys, getFieldDefinition, includeSuggestions]);

  const search = useFuzzySearch(searchableItems, FUZZY_SEARCH_OPTIONS);

  return useMemo(() => {
    if (!filterValue || !search) {
      if (!filterKeySections.length) {
        return flatKeys
          .map(key => createItem(key, getFieldDefinition(key.key)))
          .sort((a, b) => a.textValue.localeCompare(b.textValue));
      }

      const filterSectionKeys = [
        ...new Set(filterKeySections.flatMap(section => section.children)),
      ].slice(0, 50);

      return filterSectionKeys
        .map(key => filterKeys[key])
        .filter(defined)
        .map(key => createItem(key, getFieldDefinition(key.key)));
    }

    const searched = search.search(filterValue);

    const keyItems = searched
      .map(({item}) => item)
      .filter(item => item.type === 'key' && filterKeys[item.item.key])
      .map(({item}) => {
        return createItem(filterKeys[item.key]!, getFieldDefinition(item.key));
      });

    if (includeSuggestions) {
      const rawSearchSection: KeySectionItem = {
        key: 'raw-search',
        value: 'raw-search',
        label: '',
        options: [createRawSearchItem(inputValue)],
        type: 'section',
      };

      const shouldIncludeRawSearch =
        !disallowFreeText &&
        inputValue &&
        !isQuoted(inputValue) &&
        (!keyItems.length || inputValue.trim().includes(' ')) &&
        !replaceRawSearchKeys?.length;

      let rawSearchFilterHasValueItems: RawSearchFilterHasValueItem[] = [];
      if (hasWildcardSearch) {
        rawSearchFilterHasValueItems =
          replaceRawSearchKeys?.map(key => {
            return createRawSearchFilterHasValueItem(key, inputValue);
          }) ?? [];
      }

      const rawSearchFilterIsValueItems =
        replaceRawSearchKeys?.map(key => {
          const value = inputValue?.includes(' ')
            ? `"${inputValue.replace(/"/g, '')}"`
            : inputValue;

          return createRawSearchFilterIsValueItem(key, value);
        }) ?? [];

      const rawSearchReplacements: KeySectionItem = {
        key: 'raw-search-filter-values',
        value: 'raw-search-filter-values',
        label: '',
        options: [...rawSearchFilterHasValueItems, ...rawSearchFilterIsValueItems],
        type: 'section',
      };

      const shouldReplaceRawSearch =
        !disallowFreeText &&
        inputValue &&
        !isQuoted(inputValue) &&
        (!keyItems.length || inputValue.trim().includes(' ')) &&
        !!replaceRawSearchKeys?.length;

      const keyItemsSection: KeySectionItem = {
        key: 'key-items',
        value: 'key-items',
        label: '',
        options: keyItems,
        type: 'section',
      };

      const shouldShowMatchKeySuggestions =
        !disallowFreeText &&
        inputValue &&
        !isQuoted(inputValue) &&
        (!keyItems.length || inputValue.trim().includes(' ')) &&
        !!matchKeySuggestions?.length &&
        matchKeySuggestions.some(suggestion => suggestion.valuePattern.test(inputValue));

      let matchKeySuggestionsOptions: SearchKeyItem[] = [];
      if (shouldShowMatchKeySuggestions && matchKeySuggestions) {
        matchKeySuggestionsOptions = matchKeySuggestions
          ?.filter(suggestion => suggestion.valuePattern.test(inputValue))
          .map(suggestion => createFilterValueItem(suggestion.key, inputValue));
      }

      const matchKeySuggestionsSection: KeySectionItem = {
        key: 'key-matched-suggestions',
        value: 'key-matched-suggestions',
        label: '',
        options: matchKeySuggestionsOptions,
        type: 'section',
      };

      const askSeerItem = [];
      if (enableAISearch) {
        askSeerItem.push(
          gaveSeerConsent ? createAskSeerItem() : createAskSeerConsentItem()
        );
      }

      const {shouldShowAtTop, suggestedFiltersSection} =
        getValueSuggestionsFromSearchResult(searched);

      return [
        ...(shouldShowMatchKeySuggestions ? [matchKeySuggestionsSection] : []),
        ...(shouldShowAtTop && suggestedFiltersSection ? [suggestedFiltersSection] : []),
        ...(shouldReplaceRawSearch ? [rawSearchReplacements] : []),
        ...(shouldIncludeRawSearch ? [rawSearchSection] : []),
        keyItemsSection,
        ...(!shouldShowAtTop && suggestedFiltersSection ? [suggestedFiltersSection] : []),
        ...askSeerItem,
      ];
    }

    return keyItems;
  }, [
    disallowFreeText,
    enableAISearch,
    filterKeySections,
    filterKeys,
    filterValue,
    flatKeys,
    gaveSeerConsent,
    getFieldDefinition,
    hasWildcardSearch,
    includeSuggestions,
    inputValue,
    matchKeySuggestions,
    replaceRawSearchKeys,
    search,
  ]);
}
