// Helper, der vom inline-Script aufgerufen werden kann, um das Kontextmenü zu initialisieren.
// Er hängt den Klick-Handler an den globalen Button des Menüs an.
(function(){
  document.addEventListener('DOMContentLoaded', () => {
    const menu = document.getElementById('inbox_context_menu');
    const btn = menu ? menu.querySelector('#ctx_toggle_read') : null;
    if(!menu || !btn) return;
    btn.addEventListener('click', async () => {
      try{
        const item = window.inboxContextMenuCurrentItem;
        if(!item || !item.email || !item.row) return;
        const it = item.email;
        const div = item.row;
        const newSeen = !it.is_read;
        await fetch('/api/emails/seen', {
          method: 'POST',
          headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ uid: it.uid, seen: newSeen })
        });
        it.is_read = newSeen ? 1 : 0;
        if(newSeen){
          div.classList.remove('unseen');
        } else {
          div.classList.add('unseen');
        }
      }catch(_e){}
      menu.style.display = 'none';
    });
  });
})();
