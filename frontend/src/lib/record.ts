/** Recording mode for the demo video: open the app with ?record=1 (kept for the browser tab; ?record=0 turns it off).
 *  Phone-width centred column, larger type, cards highlight as they appear. No behaviour or data changes. */
function detect(): boolean {
  const q = new URLSearchParams(window.location.search).get('record')
  if (q === '1') sessionStorage.setItem('lkd-record', '1')
  if (q === '0') sessionStorage.removeItem('lkd-record')
  return sessionStorage.getItem('lkd-record') === '1'
}

export const RECORD = detect()
if (RECORD) document.documentElement.classList.add('lkd-record')
