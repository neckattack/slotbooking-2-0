// Zentrale Icon-Registry für das Frontend (logische Namen)
window.ICON_REGISTRY = {
  mail: "mail",
  user: "user",
  eye: "eye",
  archive: "archive",
  reload: "refresh",
  filter: "filter",
};

// Lokale, sehr schlanke SVG-Implementierung für ein paar häufige Icons
// (damit kein externes CDN oder ESM-Import nötig ist)
(function(){
  const SVGs = {
    mail: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" ry="2"/><polyline points="3 7 12 13 21 7"/></svg>',
    user: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>',
    eye: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12Z"/><circle cx="12" cy="12" r="3"/></svg>',
    archive: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="4" rx="1"/><path d="M5 7v11a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7"/><path d="M10 12h4"/></svg>',
    refresh: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10"/><path d="M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/></svg>',
    filter: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12 10 19 14 21 14 12 22 3"/></svg>',
  };

  window.getIconSvg = function(name, props){
    const key = (window.ICON_REGISTRY && window.ICON_REGISTRY[name]) || name;
    const raw = SVGs[key];
    if(!raw) return '';
    const size = (props && props.size) || 18;
    // Füge width/height inline hinzu, ohne das viewBox zu verändern
    return raw.replace('<svg ', `<svg width="${size}" height="${size}" `);
  };
})();
