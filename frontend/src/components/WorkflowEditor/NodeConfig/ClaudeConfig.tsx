import GenericConfig from './GenericConfig';

interface ClaudeConfigProps {
  config: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

export default function ClaudeConfig({ config, onChange }: ClaudeConfigProps) {
  return (
    <GenericConfig
      config={config}
      onChange={onChange}
      fields={[
        {
          key: 'model',
          label: 'Model',
          type: 'select',
          options: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
          defaultValue: 'claude-sonnet-4-6',
        },
        {
          key: 'system_prompt',
          label: 'System Prompt',
          type: 'textarea',
          placeholder: 'You are a helpful assistant…',
        },
        {
          key: 'user_message',
          label: 'User Message (Jinja2 template)',
          type: 'textarea',
          placeholder: '{{ data.user_input }}',
        },
        {
          key: 'max_tokens',
          label: 'Max Tokens',
          type: 'number',
          defaultValue: 2048,
        },
        {
          key: 'temperature',
          label: 'Temperature (0–1)',
          type: 'number',
          defaultValue: 0.7,
        },
        {
          key: 'credential',
          label: 'Credential (API key name)',
          type: 'text',
          placeholder: 'my-anthropic-key',
        },
        {
          key: 'timeout_seconds',
          label: 'Timeout (seconds)',
          type: 'number',
          defaultValue: 60,
        },
        {
          key: 'retry',
          label: 'Max Retries',
          type: 'number',
          defaultValue: 2,
        },
      ]}
    />
  );
}
