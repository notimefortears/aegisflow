import GenericConfig from './GenericConfig';

const OPERATORS = [
  'equals', 'not_equals', 'contains', 'not_contains',
  'greater_than', 'less_than', 'regex_match',
  'is_empty', 'is_not_empty', 'starts_with', 'ends_with',
];

interface ConditionConfigProps {
  config: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

export default function ConditionConfig({ config, onChange }: ConditionConfigProps) {
  return (
    <GenericConfig
      config={config}
      onChange={onChange}
      fields={[
        {
          key: 'field',
          label: 'Field path (dot notation)',
          type: 'text',
          placeholder: 'data.user.age',
        },
        {
          key: 'operator',
          label: 'Operator',
          type: 'select',
          options: OPERATORS,
          defaultValue: 'equals',
        },
        {
          key: 'value',
          label: 'Compare value',
          type: 'text',
          placeholder: '18',
        },
      ]}
    />
  );
}
