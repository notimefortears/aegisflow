import GenericConfig from './GenericConfig';
import type { NodeType } from '../../../types';

const PII_CATEGORIES = [
  'email', 'phone', 'ssn', 'credit_card', 'ip_address',
  'name', 'address', 'date_of_birth', 'passport', 'medical',
];

interface SecurityNodeConfigProps {
  nodeType: NodeType;
  config: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

export default function SecurityNodeConfig({ nodeType, config, onChange }: SecurityNodeConfigProps) {
  if (nodeType === 'pii_scanner') {
    return (
      <GenericConfig
        config={config}
        onChange={onChange}
        fields={[
          { key: 'action', label: 'Action', type: 'select', options: ['allow', 'block', 'redact', 'alert'], defaultValue: 'alert' },
          { key: 'fail_on_detection', label: 'Fail on detection', type: 'boolean', defaultValue: false },
        ]}
      />
    );
  }

  if (nodeType === 'injection_guard') {
    return (
      <GenericConfig
        config={config}
        onChange={onChange}
        fields={[
          { key: 'scan_field', label: 'Field to scan', type: 'text', placeholder: 'data.user_input' },
          { key: 'threshold', label: 'Risk threshold (0–1)', type: 'number', defaultValue: 0.7 },
        ]}
      />
    );
  }

  if (nodeType === 'human_gate') {
    return (
      <GenericConfig
        config={config}
        onChange={onChange}
        fields={[
          { key: 'approvers', label: 'Approver emails (comma-separated)', type: 'text', placeholder: 'alice@co.com,bob@co.com' },
          { key: 'timeout_hours', label: 'Timeout (hours)', type: 'number', defaultValue: 24 },
          { key: 'message', label: 'Approval request message', type: 'textarea', placeholder: 'Please review and approve…' },
        ]}
      />
    );
  }

  return null;
}
