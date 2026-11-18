<template>
  <GenericPage
    :get-entities="getTagged"
    :empty="
      tag
        ? {
            icon: LucideTag,
            title: __('Nothing tagged {0}').format(tag),
            description: __('Files you can open that carry this tag appear here.'),
          }
        : {
            icon: LucideTag,
            title: __('No tags yet'),
            description: __('Right-click a file and choose Tags to add one.'),
          }
    "
  />
</template>

<script setup>
import GenericPage from '@/components/GenericPage.vue'
import { getTagged } from '@/resources/files'
import LucideTag from '~icons/lucide/tag'
import { watch } from 'vue'
import { useStore } from 'vuex'

const props = defineProps({
  tag: { type: String, required: false },
})
const store = useStore()

watch(
  () => props.tag,
  (tag) => {
    // GenericPage refetches when the resource params change through its own watcher;
    // set the tag first so that fetch already carries it.
    getTagged.params = { ...getTagged.params, tag: tag || '' }
    if (getTagged.fetched) getTagged.fetch(getTagged.params)
    store.commit(
      'setBreadcrumbs',
      [
        { label: __('Tags'), name: 'Tags', route: { name: 'Tags' } },
        tag && { label: tag, name: tag, route: { name: 'Tags', params: { tag } } },
      ].filter(Boolean)
    )
  },
  { immediate: true }
)
</script>
