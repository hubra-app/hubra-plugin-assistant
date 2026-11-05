import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, Button, CloseButton, Group, Paper, Select, SimpleGrid, Stack, Text, TextInput, Textarea } from '@mantine/core'
import { IconCopy, IconSettings, IconSparkles } from '@tabler/icons-react'
import { ErrorBanner, Field, LoadingSpinner, PageHead, Seg, formatDateTime, useT, useToast } from '@hubra/plugin-sdk'
import {
  KINDS,
  LANGUAGES,
  QK,
  createDraft,
  deleteDraft,
  errorText,
  getOptions,
  listDrafts,
  type Draft,
  type Kind,
  type Language,
  type Length,
  type Options,
} from './api'

const NOTES_LIMIT = 4000
const MINUTES_LIMIT = 60000

/** Notes in, a draft out: the board's writing help. */
export function AssistantScreen() {
  const { t } = useT()
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const drafts = useQuery({ queryKey: QK.drafts, queryFn: listDrafts })

  const err = options.error || drafts.error
  if (err) return <ErrorBanner message={errorText(err)} onRetry={() => (options.refetch(), drafts.refetch())} />
  if (!options.data || !drafts.data) return <LoadingSpinner />

  return (
    <>
      <PageHead title={t('assistant.title')} desc={t('assistant.desc')} />
      {!options.data.ready ? <NotReady options={options.data} /> : <Writer options={options.data} drafts={drafts.data} />}
    </>
  )
}

function NotReady({ options }: { options: Options }) {
  const { t } = useT()
  const navigate = useNavigate()
  return (
    <Paper withBorder radius="md" p="lg" maw={720}>
      <Text fw={700} mb="xs">
        {t('assistant.setupTitle')}
      </Text>
      <Text size="sm" mb="sm">
        {t('assistant.setupBody')}
      </Text>
      <Stack gap={4} mb="md">
        <Text size="sm">{(options.consent ? '✓ ' : '○ ') + t('assistant.setupConsent')}</Text>
        <Text size="sm">{(options.hasKey ? '✓ ' : '○ ') + t('assistant.setupKey')}</Text>
      </Stack>
      <Text size="xs" c="dimmed" mb="md">
        {t('assistant.privacy')}
      </Text>
      <Button leftSection={<IconSettings size={16} />} onClick={() => navigate('/app/settings/modules')}>
        {t('assistant.toSettings')}
      </Button>
    </Paper>
  )
}

function Writer({ options, drafts }: { options: Options; drafts: Draft[] }) {
  const { t } = useT()
  const qc = useQueryClient()
  const { notify } = useToast()
  const [kind, setKind] = useState<Kind>('post')
  const [language, setLanguage] = useState<Language>('de')
  const [length, setLength] = useState<Length>('medium')
  const [eventId, setEventId] = useState<string | null>(null)
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Draft | null>(drafts[0] ?? null)
  const [title, setTitle] = useState(result?.title ?? '')
  const [body, setBody] = useState(result?.body ?? '')
  const limit = kind === 'minutes' ? MINUTES_LIMIT : NOTES_LIMIT

  const show = (d: Draft) => {
    setResult(d)
    setTitle(d.title ?? '')
    setBody(d.body ?? '')
  }

  const write = async () => {
    setBusy(true)
    setError(null)
    try {
      const d = await createDraft({ kind, language, length, notes, eventId: eventId ? Number(eventId) : null })
      show(d)
      qc.invalidateQueries({ queryKey: QK.drafts })
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(title ? `${title}\n\n${body}` : body)
      notify('success', t('assistant.copied'))
    } catch {
      notify('error', t('assistant.copyFailed'))
    }
  }

  const remove = async (d: Draft) => {
    try {
      await deleteDraft(d.id)
      if (result?.id === d.id) (setResult(null), setTitle(''), setBody(''))
      qc.invalidateQueries({ queryKey: QK.drafts })
    } catch (e) {
      notify('error', errorText(e))
    }
  }

  return (
    <Stack gap="lg">
      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <Stack gap="md">
          <Field label={t('assistant.what')}>
            <Seg value={kind} onChange={(v) => setKind(v as Kind)} options={KINDS.map((k) => ({ value: k, label: t(`assistant.kind.${k}`) }))} />
          </Field>
          <Group grow align="flex-start">
            <Select
              label={t('assistant.language')}
              value={language}
              onChange={(v) => v && setLanguage(v as Language)}
              data={LANGUAGES.map((l) => ({ value: l, label: t(`assistant.lang.${l}`) }))}
              allowDeselect={false}
            />
            {kind !== 'minutes' && (
              <Select
                label={t('assistant.event')}
                placeholder={t('assistant.noEvent')}
                value={eventId}
                onChange={setEventId}
                data={options.events.map((e) => ({ value: String(e.id), label: `${e.date.split('-').reverse().join('.')} · ${e.title}` }))}
                searchable
                clearable
              />
            )}
          </Group>
          <Field label={t('assistant.length')}>
            <Seg
              value={length}
              onChange={(v) => setLength(v as Length)}
              options={(['short', 'medium', 'long'] as const).map((l) => ({ value: l, label: t(`assistant.len.${l}`) }))}
            />
          </Field>
          <Field label={kind === 'minutes' ? t('assistant.minutes') : t('assistant.notes')}>
            <Textarea
              value={notes}
              onChange={(e) => setNotes(e.currentTarget.value)}
              autosize
              minRows={kind === 'minutes' ? 10 : 6}
              maxRows={20}
              maxLength={limit}
              placeholder={t(`assistant.hint.${kind}`)}
            />
          </Field>
          <Group justify="space-between" align="flex-start" wrap="nowrap">
            <Text size="xs" c="dimmed">
              {t('assistant.sentNote')}
            </Text>
            <Button leftSection={<IconSparkles size={16} />} loading={busy} disabled={!notes.trim()} onClick={write} style={{ flexShrink: 0 }}>
              {t('assistant.write')}
            </Button>
          </Group>
          {error && (
            <Alert color="red" variant="light">
              {error}
            </Alert>
          )}
        </Stack>

        <Paper withBorder radius="md" p="md">
          {!result ? (
            <Text size="sm" c="dimmed">
              {t('assistant.empty')}
            </Text>
          ) : (
            <Stack gap="sm">
              <Group justify="space-between">
                <Text fw={700}>{t('assistant.draft')}</Text>
                <Button size="xs" variant="light" leftSection={<IconCopy size={14} />} onClick={copy}>
                  {t('assistant.copy')}
                </Button>
              </Group>
              <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} aria-label={t('assistant.titleLabel')} fw={700} />
              <Textarea value={body} onChange={(e) => setBody(e.currentTarget.value)} autosize minRows={12} aria-label={t('assistant.bodyLabel')} />
              <Text size="xs" c="dimmed">
                {t('assistant.checkIt')}
              </Text>
            </Stack>
          )}
        </Paper>
      </SimpleGrid>

      {drafts.length > 0 && (
        <section>
          <Text fw={700} mb="xs">
            {t('assistant.recent')}
          </Text>
          <Stack gap={6}>
            {drafts.map((d) => (
              <Paper
                key={d.id}
                withBorder
                radius="md"
                px="md"
                py="xs"
                style={{ cursor: 'pointer', borderColor: result?.id === d.id ? 'var(--mantine-primary-color-filled)' : undefined }}
                onClick={() => show(d)}
              >
                <Group justify="space-between" wrap="nowrap">
                  <div style={{ minWidth: 0 }}>
                    <Text size="sm" fw={600} truncate>
                      {d.title || t(`assistant.kind.${d.kind}`)}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {t(`assistant.kind.${d.kind}`)} · {formatDateTime(d.createdAt ?? '')}
                    </Text>
                  </div>
                  <CloseButton
                    aria-label={t('assistant.delete')}
                    onClick={(e) => {
                      e.stopPropagation()
                      remove(d)
                    }}
                  />
                </Group>
              </Paper>
            ))}
          </Stack>
        </section>
      )}
    </Stack>
  )
}
