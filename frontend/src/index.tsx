import { registerPlugin } from '@hubra/plugin-sdk'
import { IconSparkles } from '@tabler/icons-react'
import { AssistantScreen } from './AssistantScreen'
import translations from './translations.json'

registerPlugin({
  id: 'assistant',
  routes: [{ path: 'assistant', module: 'assistant', perm: 'assistant.drafts.update', component: AssistantScreen }],
  // The nav entry in hubra_assistant/__init__.py names this icon.
  icons: { sparkles: IconSparkles },
  translations,
})
