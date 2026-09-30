import { useEffect, useRef, type ReactNode } from 'react'
import { useLanguage } from '../i18n'

export function CartDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const { t } = useLanguage()
  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (open && !element.open) element.showModal()
    else if (!open && element.open) element.close()
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = previousOverflow }
  }, [open])
  return <dialog ref={dialog} className="cart-drawer" aria-labelledby="cart-heading" onCancel={onClose} onClose={onClose} onClick={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <div className="cart-drawer__content">
      <button className="close-button cart-drawer__close" type="button" onClick={onClose}>{t('Close cart')}</button>
      {open && children}
    </div>
  </dialog>
}
