// Copyright (c) 2026, Lifegence Corporation and Contributors
// Collabora Online integration: off unless the site config sets drive_collabora_url
import { createResource } from 'frappe-ui'

export const collabora = createResource({
  url: 'lifegence_drive.api.wopi.settings',
  cache: 'collabora-settings',
  auto: true,
})

const extension = (name) => (name || '').split('.').pop().toLowerCase()

// Uploaded Office files only; Writer and Slides documents have their own editors
export const canUseCollabora = (entity) =>
  !!collabora.data?.enabled &&
  !!entity &&
  !entity.is_folder &&
  !['Writer Document', 'Presentation'].includes(entity.content_doctype) &&
  collabora.data.extensions.includes(extension(entity.file_name))

export const openInCollabora = (entity) =>
  window.open(`/drive_office?file=${encodeURIComponent(entity.name)}`, '_blank')

export const collaboraPreviewUrl = (entity) =>
  `/api/method/lifegence_drive.api.wopi.preview_pdf?entity_name=${encodeURIComponent(entity.name)}`
