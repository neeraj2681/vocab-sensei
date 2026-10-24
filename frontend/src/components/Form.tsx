import type { InputHTMLAttributes, ReactNode } from 'react'

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
}

export function Field({ label, id, ...input }: FieldProps) {
  const fieldId = id ?? input.name
  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <input id={fieldId} {...input} />
    </div>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="form-error">
      {message}
    </p>
  )
}

export function AuthCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="auth-card">
      <h2>{title}</h2>
      {children}
    </section>
  )
}
