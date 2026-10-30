const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

export const formatWhen = (iso: string) => dateFormat.format(new Date(iso))
