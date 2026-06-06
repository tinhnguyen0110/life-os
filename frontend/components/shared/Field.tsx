"use client";
/* ============================================================
   Shared form primitives (S12) — Field / TextInput / NumberInput / Select / Toggle.
   First write/forms screen in life-os. Per-field 422 echo: pass `error` (from
   ApiError.fieldErrors()[name]) → the field shows an inline red message + red border.
   Controlled inputs (value + onChange) — NO optimistic state; the parent owns the
   value and only commits on save (fail-closed: mutate→await→refetch).
   ============================================================ */
import type { ReactNode, ChangeEvent } from "react";

interface FieldProps {
  label: string;
  htmlFor?: string;
  error?: string | null;
  hint?: string;
  children: ReactNode;
  testId?: string;
}

/** Label + control + optional inline error (per-field 422) / hint. */
export function Field({ label, htmlFor, error, hint, children, testId }: FieldProps) {
  return (
    <div className={`field${error ? " has-err" : ""}`} data-testid={testId}>
      <label className="flabel" htmlFor={htmlFor}>{label}</label>
      {children}
      {error ? (
        <span className="ferr" data-testid={testId ? `${testId}-error` : undefined}>{error}</span>
      ) : hint ? (
        <span className="fhint">{hint}</span>
      ) : null}
    </div>
  );
}

interface TextInputProps {
  id?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  maxLength?: number;
  disabled?: boolean;
  invalid?: boolean;
  testId?: string;
}

export function TextInput({ id, value, onChange, placeholder, maxLength, disabled, invalid, testId }: TextInputProps) {
  return (
    <input
      id={id}
      className="finput"
      type="text"
      value={value}
      placeholder={placeholder}
      maxLength={maxLength}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      data-testid={testId}
    />
  );
}

interface NumberInputProps {
  id?: string;
  value: number | "";
  onChange: (v: number | "") => void;
  min?: number;
  max?: number;
  disabled?: boolean;
  invalid?: boolean;
  testId?: string;
}

/** Numeric input — empty string allowed mid-edit (don't coerce "" to 0); parent
 *  validates on save. Sends number when parseable, "" when blank. */
export function NumberInput({ id, value, onChange, min, max, disabled, invalid, testId }: NumberInputProps) {
  return (
    <input
      id={id}
      className="finput num"
      type="number"
      value={value === "" ? "" : String(value)}
      min={min}
      max={max}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(e: ChangeEvent<HTMLInputElement>) => {
        const raw = e.target.value;
        if (raw === "") return onChange("");
        const n = Number(raw);
        onChange(Number.isNaN(n) ? "" : n);
      }}
      data-testid={testId}
    />
  );
}

interface SelectProps {
  id?: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  disabled?: boolean;
  invalid?: boolean;
  testId?: string;
}

export function Select({ id, value, onChange, options, disabled, invalid, testId }: SelectProps) {
  return (
    <select
      id={id}
      className="finput"
      value={value}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      data-testid={testId}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>{o.label}</option>
      ))}
    </select>
  );
}

interface ToggleProps {
  on: boolean;
  onChange: (next: boolean) => void;
  disabled?: boolean;
  label?: string; // a11y label
  testId?: string;
}

/** On/off switch — the mock's .toggle, as an accessible button. Controlled. */
export function Toggle({ on, onChange, disabled, label, testId }: ToggleProps) {
  return (
    <button
      type="button"
      className={`toggle${on ? " on" : ""}`}
      role="switch"
      aria-checked={on}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!on)}
      data-testid={testId}
    />
  );
}
