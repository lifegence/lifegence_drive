<template>
  <Dialog
    v-model="open"
    :options="{
      title: entities.length > 1 ? __('Tags ({0} items)').format(entities.length) : __('Tags'),
      size: 'sm',
    }"
    @close="dialogType = ''"
  >
    <template #body-content>
      <p v-if="entities.length > 1" class="text-sm text-ink-gray-5 mb-3">
        {{ __('Tags you add or remove here apply to every selected item.') }}
      </p>
      <div class="flex flex-wrap gap-1.5 mb-3 min-h-6">
        <span
          v-for="tag in tags"
          :key="tag"
          class="inline-flex items-center gap-1 rounded bg-surface-gray-2 px-2 py-0.5 text-sm text-ink-gray-8"
        >
          {{ tag }}
          <button
            class="text-ink-gray-5 hover:text-ink-gray-8"
            :aria-label="__('Remove tag {0}').format(tag)"
            :disabled="busy"
            @click="remove(tag)"
          >
            <LucideX class="size-3" />
          </button>
        </span>
        <span v-if="!tags.length" class="text-sm text-ink-gray-5">
          {{ __('No tags yet') }}
        </span>
      </div>
      <div class="flex gap-2">
        <TextInput
          v-model="newTag"
          v-focus
          class="grow"
          type="text"
          list="drive-tag-options"
          maxlength="140"
          :placeholder="__('Add a tag')"
          @keydown.enter="onEnter"
        />
        <Button
          variant="solid"
          :disabled="!cleaned || busy"
          :loading="addTag.loading"
          @click="add"
        >
          {{ __('Add') }}
        </Button>
      </div>
      <datalist id="drive-tag-options">
        <option v-for="t in suggestions" :key="t" :value="t" />
      </datalist>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Dialog, Button, TextInput, toast } from 'frappe-ui'
import { allTags, addTag, removeTag } from '../js/resources'
import LucideX from '~icons/lucide/x'

const props = defineProps({ entities: Array })
const emit = defineEmits(['success'])
const dialogType = defineModel()
const open = ref(true)
const newTag = ref('')

// Show only the tags every selected item already has
const commonTags = (entities) => {
  const [first, ...rest] = entities
  return (first?.tags || []).filter((t) =>
    rest.every((e) => (e.tags || []).some((x) => x.toLowerCase() === t.toLowerCase()))
  )
}
const tags = ref(commonTags(props.entities))

if (!allTags.fetched) allTags.fetch()
const suggestions = computed(() =>
  (allTags.data || [])
    .map((t) => t.tag)
    .filter((t) => !tags.value.some((x) => x.toLowerCase() === t.toLowerCase()))
)

const cleaned = computed(() => newTag.value.split(/\s+/).filter(Boolean).join(' '))
const busy = computed(() => addTag.loading || removeTag.loading)
const names = () => props.entities.map((e) => e.name)

// Write the server's answer back onto the rows so lists and chips update in place
const apply = (result) => {
  props.entities.forEach((e) => {
    if (result[e.name]) e.tags = result[e.name]
  })
  tags.value = commonTags(props.entities)
  emit('success', props.entities)
  allTags.fetch()
}

const add = () => {
  const tag = cleaned.value
  if (!tag || busy.value) return
  if (tag.includes(',')) {
    toast.error(__('Tags cannot contain commas'))
    return
  }
  addTag.submit(
    { entity_names: names(), tag },
    {
      onSuccess: (result) => {
        newTag.value = ''
        apply(result)
      },
    }
  )
}

// Enter that confirms an IME conversion (e.g. Japanese input) must not add the tag
const onEnter = (e) => {
  if (e.isComposing || e.keyCode === 229) return
  e.preventDefault()
  add()
}

const remove = (tag) => {
  removeTag.submit({ entity_names: names(), tag }, { onSuccess: apply })
}
</script>
