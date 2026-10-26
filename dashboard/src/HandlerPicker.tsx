import type { Handler } from "./api";

export function HandlerPicker({
  handlers,
  value,
  onChange,
}: Readonly<{
  handlers: Handler[];
  value: string;
  onChange: (id: string) => void;
}>) {
  return (
    <label className="field">
      <span>Handler</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {handlers.map((handler) => (
          <option key={handler.handler_id} value={handler.handler_id}>
            {handler.name}, {handler.role}
          </option>
        ))}
      </select>
    </label>
  );
}
