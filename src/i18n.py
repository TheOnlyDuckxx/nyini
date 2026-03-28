from __future__ import annotations

from src.domain.enums import AppLanguage, MediaKind, Orientation, SmartCollection, SortField, ThemeMode, WallpaperSourceKind


_CURRENT_LANGUAGE = AppLanguage.FR

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "Francais": {"en": "French"},
    "Anglais": {"en": "English"},
    "General": {"fr": "General"},
    "Appearance": {"fr": "Apparence"},
    "Apparence": {"en": "Appearance"},
    "Integrations": {"en": "Integrations"},
    "Raccourcis": {"en": "Shortcuts"},
    "Shortcuts": {"fr": "Raccourcis"},
    "Parametres": {"en": "Settings"},
    "Settings": {"fr": "Parametres"},
    "Theme": {"en": "Theme"},
    "Langue": {"en": "Language"},
    "Language": {"fr": "Langue"},
    "Auto (systeme)": {"en": "Auto (system)"},
    "Clair": {"en": "Light"},
    "Sombre": {"en": "Dark"},
    "Le mode auto suit `QStyleHints.colorScheme()` quand le systeme l'expose.": {
        "en": "Auto mode follows `QStyleHints.colorScheme()` when the system exposes it."
    },
    "Bibliotheque": {"en": "Library"},
    "Inbox": {"en": "Inbox"},
    "Miniatures": {"en": "Thumbnails"},
    "Polling (ms)": {"en": "Polling (ms)"},
    "Slideshow (s)": {"en": "Slideshow (s)"},
    "Backend wallpaper": {"en": "Wallpaper backend"},
    "Preset mpvpaper": {"en": "mpvpaper preset"},
    "Tri par defaut": {"en": "Default sort"},
    "Template renommage": {"en": "Rename template"},
    "Calculer les hash pendant le scan": {"en": "Compute hashes during scan"},
    "Importer automatiquement le dossier Inbox avant scan": {
        "en": "Automatically import the Inbox folder before scanning"
    },
    "Lire les previews video dans la visionneuse": {"en": "Play video previews in the viewer"},
    "Video": {"fr": "Video"},
    "Silencieux": {"en": "Silent"},
    "Pause": {"en": "Pause"},
    "Statut inconnu": {"en": "Unknown status"},
    "Oui": {"en": "Yes"},
    "Non": {"en": "No"},
    "Rate limit": {"fr": "Limite"},
    "Cle API configuree": {"en": "API key configured"},
    "Cle API": {"en": "API key"},
    "Purete par defaut": {"en": "Default purity"},
    "Ratios par defaut": {"en": "Default ratios"},
    "Resolution min": {"en": "Minimum resolution"},
    "Blacklist": {"en": "Blacklist"},
    "Gowall": {"en": "Gowall"},
    "Version": {"en": "Version"},
    "Executable": {"en": "Executable"},
    "Themes importes": {"en": "Imported themes"},
    "Statut": {"en": "Status"},
    "Action": {"en": "Action"},
    "Description": {"en": "Description"},
    "Raccourci": {"en": "Shortcut"},
    "Date": {"en": "Date"},
    "Wallpaper ID": {"fr": "ID wallpaper"},
    "Payload": {"fr": "Payload"},
    "Historique": {"en": "History"},
    "Raccourcis clavier": {"en": "Keyboard shortcuts"},
    "Visionneuse": {"en": "Viewer"},
    "Selectionnez un wallpaper": {"en": "Select a wallpaper"},
    "Plein ecran": {"en": "Fullscreen"},
    "Precedent": {"en": "Previous"},
    "Suivant": {"en": "Next"},
    "Themes Gowall": {"en": "Gowall themes"},
    "Reset zoom": {"fr": "Reinitialiser zoom"},
    "Preview video": {"fr": "Preview video", "en": "Video preview"},
    "Poster video": {"en": "Video poster"},
    "Gowall ne s'applique qu'aux wallpapers image.": {
        "en": "Gowall only applies to image wallpapers."
    },
    "Aucun wallpaper": {"en": "No wallpaper"},
    "Selectionnez un wallpaper pour inspecter ses metadonnees": {
        "en": "Select a wallpaper to inspect its metadata"
    },
    "Normal": {"en": "Normal"},
    "0 vues": {"en": "0 views"},
    "Note 0": {"en": "Rating 0"},
    "Note {rating}": {"en": "Rating {rating}"},
    "Favori": {"en": "Favorite"},
    "Notes locales": {"en": "Local notes"},
    "Enregistrer": {"en": "Save"},
    "Calculer hash": {"en": "Compute hash"},
    "Ouvrir dossier": {"en": "Open folder"},
    "Ouvrir source": {"en": "Open source"},
    "Metadonnees": {"en": "Metadata"},
    "Nom": {"en": "Name"},
    "Media": {"en": "Media"},
    "Dimensions": {"en": "Dimensions"},
    "Duree": {"en": "Duration"},
    "Orientation": {"en": "Orientation"},
    "Taille": {"en": "Size"},
    "Modifie": {"en": "Modified"},
    "Vues": {"en": "Views"},
    "Couleur moyenne": {"en": "Average color"},
    "Luminosite": {"en": "Brightness"},
    "Provenance": {"en": "Provenance"},
    "Type": {"en": "Type"},
    "Provider": {"en": "Provider"},
    "Source URL": {"en": "Source URL"},
    "Auteur": {"en": "Author"},
    "Licence": {"en": "License"},
    "Importe": {"en": "Imported"},
    "Generateur": {"en": "Generator"},
    "Edition": {"en": "Edit"},
    "Note": {"en": "Rating"},
    "Tags": {"en": "Tags"},
    "Notes": {"en": "Notes"},
    "{count} vues": {"en": "{count} views"},
    "Image": {"en": "Image"},
    "local": {"en": "Local", "fr": "Local"},
    "filesystem": {"en": "Filesystem"},
    "{count} wallpapers": {"en": "{count} wallpapers"},
    "{count} favoris": {"en": "{count} favorites"},
    "{count} non vus": {"en": "{count} unseen"},
    "{count} doublons": {"en": "{count} duplicates"},
    "Filtrer dossiers et collections": {"en": "Filter folders and collections"},
    "Toute la bibliotheque": {"en": "Entire library"},
    "Collections intelligentes": {"en": "Smart collections"},
    "Video wallpapers": {"en": "Video wallpapers"},
    "Portraits": {"en": "Portraits"},
    "Paysages": {"en": "Landscapes"},
    "Carres": {"en": "Squares"},
    "Jamais vus": {"en": "Never viewed"},
    "Notes 4-5": {"en": "Ratings 4-5"},
    "Doublons": {"en": "Duplicates"},
    "Sombres": {"en": "Dark"},
    "Anime": {"en": "Anime"},
    "Minimal": {"en": "Minimal"},
    "Sans tags": {"en": "Untagged"},
    "Recents": {"en": "Recent"},
    "No Preview": {"fr": "Pas d'apercu"},
    "Revue des doublons": {"en": "Duplicate review"},
    "Aucun doublon": {"en": "No duplicate"},
    "Suppr.": {"en": "Delete"},
    "Apercu": {"en": "Preview"},
    "Fichier": {"en": "File"},
    "Resolution": {"en": "Resolution"},
    "Score": {"en": "Score"},
    "Conserver recommande": {"en": "Keep recommended"},
    "Tout decocher": {"en": "Clear all"},
    "Supprimer coches": {"en": "Delete checked"},
    "Groupes": {"en": "Groups"},
    "{filename} ({count} fichiers)": {"en": "{filename} ({count} files)"},
    "Recommandation: conserver `{filename}` (score {score}) et verifier les autres avant suppression.": {
        "en": "Recommendation: keep `{filename}` (score {score}) and review the others before deleting."
    },
    "Wallhaven": {"en": "Wallhaven"},
    "Pret": {"en": "Ready"},
    "indisponible": {"en": "unavailable"},
    "Backend actif": {"en": "Active backend"},
    "Backend video": {"en": "Video backend"},
    "Backend video actif": {"en": "Active video backend"},
    "Session": {"en": "Session"},
    "Desktop": {"en": "Desktop"},
    "Recherche Wallhaven": {"en": "Search Wallhaven"},
    "Tout": {"en": "All"},
    "Rechercher": {"en": "Search"},
    "Page -": {"en": "Page -"},
    "Page +": {"en": "Page +"},
    "Aucun resultat": {"en": "No result"},
    "Selectionne un resultat": {"en": "Select a result"},
    "Tags Wallhaven": {"en": "Wallhaven tags"},
    "Importer vers Inbox": {"en": "Import to Inbox"},
    "Fermer": {"en": "Close"},
    "Chargement...": {"en": "Loading..."},
    "Recherche en cours": {"en": "Searching"},
    "Recherche Wallhaven...": {"en": "Searching Wallhaven..."},
    "Resultat {current}/{total}: {wallhaven_id}": {"en": "Result {current}/{total}: {wallhaven_id}"},
    "{count} resultat(s) · page {page}/{last_page} · total {total}": {
        "en": "{count} result(s) · page {page}/{last_page} · total {total}"
    },
    "Ajuste les filtres ou la recherche.": {"en": "Adjust the filters or the search."},
    "Recherche Wallhaven impossible": {"en": "Wallhaven search failed"},
    "Preview indisponible": {"en": "Preview unavailable"},
    "auteur inconnu": {"en": "unknown author"},
    "Import Wallhaven impossible": {"en": "Wallhaven import failed"},
    "Aucune preview generee": {"en": "No preview generated"},
    "Importer un theme JSON": {"en": "Import a JSON theme"},
    "Rafraichir les themes": {"en": "Refresh themes"},
    "Appliquer": {"en": "Apply"},
    "Sauvegarder dans la bibliotheque": {"en": "Save to library"},
    "Selectionne un theme": {"en": "Select a theme"},
    "Aucun theme": {"en": "No theme"},
    "Themes JSON (*.json)": {"en": "JSON themes (*.json)"},
    "Theme existant": {"en": "Existing theme"},
    "Le theme `{theme_name}` existe deja. Le remplacer ?": {
        "en": "Theme `{theme_name}` already exists. Replace it?"
    },
    "Import impossible": {"en": "Import failed"},
    "Application impossible": {"en": "Apply failed"},
    "Sauvegarde impossible": {"en": "Save failed"},
    "Aucun theme disponible": {"en": "No theme available"},
    "Generation de {count} preview(s)...": {"en": "Generating {count} preview(s)..."},
    "Preview {current}/{total}: {theme_name}": {"en": "Preview {current}/{total}: {theme_name}"},
    "Erreur: {message}": {"en": "Error: {message}"},
    "Generation terminee avec {count} erreur(s)": {"en": "Generation finished with {count} error(s)"},
    "Generation terminee": {"en": "Generation finished"},
    "Echec: {message}": {"en": "Failed: {message}"},
    "{origin_label} · {name}": {"en": "{origin_label} · {name}"},
    "Preview en attente": {"en": "Preview pending"},
    "{origin_label} · Generation en cours": {"en": "{origin_label} · Generation in progress"},
    "Preview": {"fr": "Apercu"},
    "Bienvenue dans {app_name}": {"en": "Welcome to {app_name}"},
    "Choisis les emplacements de base avant le premier scan. Tu pourras tout modifier plus tard dans les parametres.": {
        "en": "Choose the base locations before the first scan. You can change everything later in settings."
    },
    "Choisir un dossier": {"en": "Choose a folder"},
    "Parcourir": {"en": "Browse"},
    "Choisis `Auto` pour laisser l'application detecter le backend Linux le plus adapte.": {
        "en": "Choose `Auto` to let the application detect the most suitable Linux wallpaper backend."
    },
    "Le mode `Auto` detecte le backend wallpaper compatible avec ta session Linux.": {
        "en": "`Auto` detects the wallpaper backend compatible with your Linux session."
    },
    "Recherche: nom, tags, notes, chemin": {"en": "Search: name, tags, notes, path"},
    "Toutes orientations": {"en": "All orientations"},
    "Paysage": {"en": "Landscape"},
    "Toutes sources": {"en": "All sources"},
    "Local": {"en": "Local"},
    "Import manuel": {"en": "Manual import"},
    "Derive": {"en": "Derived"},
    "Note min ": {"en": "Min rating "},
    "Scanner": {"en": "Scan"},
    "Presets": {"fr": "Presets", "en": "Presets"},
    "Effacer filtres": {"en": "Clear filters"},
    "Bibliotheque locale": {"en": "Local library"},
    "{count} visibles": {"en": "{count} visible"},
    "{count} selection": {"en": "{count} selected"},
    "Mode Studio": {"en": "Studio mode"},
    "Studio": {"en": "Studio"},
    "Browser": {"fr": "Navigateur"},
    "Focus": {"en": "Focus"},
    "Sidebar": {"fr": "Volet"},
    "Inspecteur": {"en": "Inspector"},
    "{size}px": {"en": "{size}px"},
    "{count} wallpapers selectionnes": {"en": "{count} selected wallpapers"},
    "Actions selection": {"en": "Selection actions"},
    "Clic droit pour plus d'actions": {"en": "Right-click for more actions"},
    "{visible}/{total} visibles": {"en": "{visible}/{total} visible"},
    "Chargement de la bibliotheque...": {"en": "Loading library..."},
    "Configuration initiale requise": {"en": "Initial configuration required"},
    "Filtres": {"en": "Filters"},
    "Densite": {"en": "Density"},
    "Navigation": {"en": "Navigation"},
    "Actions": {"en": "Actions"},
    "Importer Inbox": {"en": "Import Inbox"},
    "Grille": {"en": "Grid"},
    "Deplacer": {"en": "Move"},
    "Renommer": {"en": "Rename"},
    "Corbeille": {"en": "Trash"},
    "Appliquer aleatoire": {"en": "Apply random"},
    "Review Inbox": {"fr": "Revue Inbox", "en": "Review Inbox"},
    "Review doublons": {"en": "Review duplicates"},
    "Rafraichir doublons": {"en": "Refresh duplicates"},
    "Slideshow": {"en": "Slideshow"},
    "Annuler": {"en": "Undo"},
    "Retablir": {"en": "Redo"},
    "Edition": {"en": "Edit"},
    "Review": {"fr": "Revue"},
    "Outils": {"en": "Tools"},
    "Actions de groupe": {"en": "Group actions"},
    "Presets de filtres": {"en": "Filter presets"},
    "Mode Browser": {"fr": "Mode Navigateur", "en": "Browser mode"},
    "Mode Focus": {"en": "Focus mode"},
    "Mode Custom": {"fr": "Mode Personnalise", "en": "Custom mode"},
    "Layout {preset}": {"en": "Layout {preset}"},
    "Recherche: {query}": {"en": "Search: {query}"},
    "Source: {source}": {"en": "Source: {source}"},
    "Favoris seulement": {"en": "Favorites only"},
    "Orientation: {orientation}": {"en": "Orientation: {orientation}"},
    "Note min {rating}": {"en": "Min rating {rating}"},
    "{label} x": {"en": "{label} x"},
    "Collection: {label}": {"en": "Collection: {label}"},
    "Dossier: {folder}": {"en": "Folder: {folder}"},
    "Aucun wallpaper selectionne": {"en": "No wallpaper selected"},
    "{current_label} · Densite {size}px · {count} resultat(s)": {
        "en": "{current_label} · Density {size}px · {count} result(s)"
    },
    "Appliquer le preset": {"en": "Apply preset"},
    "Sauver le filtre courant": {"en": "Save current filter"},
    "Supprimer le preset": {"en": "Delete preset"},
    "Sauver preset": {"en": "Save preset"},
    "Nom du preset": {"en": "Preset name"},
    "Preset enregistre: {preset_name}": {"en": "Preset saved: {preset_name}"},
    "Preset applique: {preset_name}": {"en": "Preset applied: {preset_name}"},
    "Preset supprime: {preset_name}": {"en": "Preset deleted: {preset_name}"},
    "Filtres effaces": {"en": "Filters cleared"},
    "Note {rating} appliquee": {"en": "Rating {rating} applied"},
    "Tags rapides": {"en": "Quick tags"},
    "Tags (separes par des virgules)": {"en": "Tags (comma separated)"},
    "Tags mis a jour": {"en": "Tags updated"},
    "Inbox vide": {"en": "Inbox empty"},
    "Review Inbox actif": {"en": "Inbox review active"},
    "{count} wallpaper(s) importes depuis Wallhaven": {"en": "{count} wallpaper(s) imported from Wallhaven"},
    "Ouvrir": {"en": "Open"},
    "Afficher ce dossier": {"en": "Show this folder"},
    "Ouvrir le dossier": {"en": "Open folder"},
    "Quick preview": {"fr": "Apercu rapide", "en": "Quick preview"},
    "Gowall": {"en": "Gowall"},
    "Gowall absent": {"en": "Gowall missing"},
    "Les themes Gowall ne s'appliquent qu'aux wallpapers image.": {
        "en": "Gowall themes only apply to image wallpapers."
    },
    "Rendu Gowall sauvegarde: {filename}": {"en": "Saved Gowall render: {filename}"},
    "Theme Gowall applique sur {filename}: {output_name}": {
        "en": "Gowall theme applied on {filename}: {output_name}"
    },
    "Prechargement viewer": {"en": "Viewer preload"},
    "Zoom {percent}%": {"en": "Zoom {percent}%"},
    "{job_name}: {message}": {"en": "{job_name}: {message}"},
    "Scan en cours...": {"en": "Scan in progress..."},
    "Scan bibliotheque": {"en": "Library scan"},
    "Scan {current}/{total}: {filename}": {"en": "Scan {current}/{total}: {filename}"},
    "Scan termine: {scanned} indexes, {imported} ajoutes, {updated} mis a jour, {removed} retires": {
        "en": "Scan finished: {scanned} indexed, {imported} added, {updated} updated, {removed} removed"
    },
    ", {count} importes depuis Inbox": {"en": ", {count} imported from Inbox"},
    ", {count} erreurs": {"en": ", {count} errors"},
    "Echec du scan": {"en": "Scan failed"},
    "Scan impossible": {"en": "Scan failed"},
    "Choisir le dossier cible": {"en": "Choose target folder"},
    "Conflit de deplacement": {"en": "Move conflict"},
    "Deplacement": {"en": "Move"},
    "Deplacement vers {target}": {"en": "Moved to {target}"},
    "Renommage": {"en": "Rename"},
    "Template de renommage": {"en": "Rename template"},
    "Conflit de renommage": {"en": "Rename conflict"},
    "Renommage termine": {"en": "Rename finished"},
    "{count} destination(s) existent deja.\nExemple: {example}\n\nChoisis la strategie a appliquer.": {
        "en": "{count} destination(s) already exist.\nExample: {example}\n\nChoose the strategy to apply."
    },
    "Garder les deux": {"en": "Keep both"},
    "Remplacer": {"en": "Replace"},
    "Suppression": {"en": "Delete"},
    "Supprimer vers la corbeille": {"en": "Move to trash"},
    "Envoyer {count} wallpapers vers la corbeille ?": {"en": "Send {count} wallpapers to trash?"},
    "Aucun doublon a revoir": {"en": "No duplicate to review"},
    "Aucun doublon selectionne pour suppression": {"en": "No duplicate selected for deletion"},
    "{count} doublon(s) envoyes vers la corbeille": {"en": "{count} duplicate(s) sent to trash"},
    "Hash calcule": {"en": "Hash computed"},
    "Doublons actualises": {"en": "Duplicates refreshed"},
    "Inbox vide ou inexistante": {"en": "Inbox empty or missing"},
    "{count} fichier(s) importes depuis Inbox": {"en": "{count} file(s) imported from Inbox"},
    "Application impossible": {"en": "Apply failed"},
    "Video wallpaper applique: {filename} ({preset})": {"en": "Video wallpaper applied: {filename} ({preset})"},
    "Wallpaper applique: {filename}": {"en": "Wallpaper applied: {filename}"},
    "Application aleatoire impossible": {"en": "Random apply failed"},
    "Wallpaper aleatoire applique: {filename}": {"en": "Random wallpaper applied: {filename}"},
    "Slideshow arrete": {"en": "Slideshow stopped"},
    "Pas assez d'images pour un slideshow": {"en": "Not enough images for a slideshow"},
    "Slideshow actif": {"en": "Slideshow active"},
    "Recherche": {"en": "Search"},
    "Placer le focus dans la recherche": {"en": "Focus the search field"},
    "Relancer l'indexation de la bibliotheque": {"en": "Restart library indexing"},
    "Importer les images du dossier Inbox": {"en": "Import images from the Inbox folder"},
    "Vue grille": {"en": "Grid view"},
    "Afficher la grille": {"en": "Show the grid"},
    "Ouvrir l'image courante dans la visionneuse": {"en": "Open the current image in the viewer"},
    "Basculer le favori sur la selection": {"en": "Toggle favorite on the selection"},
    "Deplacer les wallpapers selectionnes": {"en": "Move selected wallpapers"},
    "Renommer les wallpapers selectionnes": {"en": "Rename selected wallpapers"},
    "Envoyer la selection vers la corbeille": {"en": "Send the selection to trash"},
    "Modifier rapidement les tags du wallpaper courant": {"en": "Quickly edit tags for the current wallpaper"},
    "Selectionner ou afficher le wallpaper precedent": {"en": "Select or show the previous wallpaper"},
    "Selectionner ou afficher le wallpaper suivant": {"en": "Select or show the next wallpaper"},
    "Choisir un wallpaper aleatoire dans le filtre courant": {"en": "Pick a random wallpaper from the current filter"},
    "Ouvrir le filtre Inbox et la visionneuse": {"en": "Open the Inbox filter and the viewer"},
    "Ouvrir la revue des doublons": {"en": "Open duplicate review"},
    "Attribuer la note 1 au wallpaper courant": {"en": "Assign rating 1 to the current wallpaper"},
    "Attribuer la note 2 au wallpaper courant": {"en": "Assign rating 2 to the current wallpaper"},
    "Attribuer la note 3 au wallpaper courant": {"en": "Assign rating 3 to the current wallpaper"},
    "Attribuer la note 4 au wallpaper courant": {"en": "Assign rating 4 to the current wallpaper"},
    "Attribuer la note 5 au wallpaper courant": {"en": "Assign rating 5 to the current wallpaper"},
    "Calculer les hash manquants et mettre a jour les doublons": {
        "en": "Compute missing hashes and refresh duplicates"
    },
    "Activer ou couper le slideshow": {"en": "Toggle slideshow"},
    "Ouvrir l'historique des operations": {"en": "Open operation history"},
    "Ouvrir les parametres": {"en": "Open settings"},
    "Afficher la liste des raccourcis": {"en": "Show the list of shortcuts"},
    "scan": {"en": "Scan", "fr": "Scan"},
    "gowall_import_theme": {"en": "Import Gowall theme", "fr": "Import theme Gowall"},
    "wallhaven_download": {"en": "Wallhaven download", "fr": "Telechargement Wallhaven"},
    "save_gowall_preview": {"en": "Save Gowall preview", "fr": "Sauvegarde preview Gowall"},
    "import_inbox": {"en": "Import Inbox", "fr": "Import Inbox"},
    "hash_library": {"en": "Hash library", "fr": "Hash bibliotheque"},
    "favorite": {"en": "Favorite", "fr": "Favori"},
    "update_details": {"en": "Update details", "fr": "Maj details"},
    "move": {"en": "Move", "fr": "Deplacement"},
    "trash": {"en": "Trash", "fr": "Corbeille"},
    "restore": {"en": "Restore", "fr": "Restauration"},
    "apply_wallpaper": {"en": "Apply wallpaper", "fr": "Application wallpaper"},
    "apply_gowall_theme": {"en": "Apply Gowall theme", "fr": "Application theme Gowall"},
    "Wallhaven disponible avec cle API configuree.": {"en": "Wallhaven available with API key configured."},
    "Wallhaven disponible en mode SFW sans cle API.": {"en": "Wallhaven available in SFW mode without an API key."},
    "gowall n'est pas installe. Installe-le pour utiliser les themes.": {
        "en": "gowall is not installed. Install it to use themes."
    },
    "gowall disponible ({version})": {"en": "gowall available ({version})"},
    "gowall disponible": {"en": "gowall available"},
    "Importe": {"en": "Imported"},
    "Requiert plasma-apply-wallpaperimage": {"en": "Requires plasma-apply-wallpaperimage"},
    "Requiert gsettings": {"en": "Requires gsettings"},
    "Requiert xfconf-query sur une session XFCE": {"en": "Requires xfconf-query on an XFCE session"},
    "Requiert swaymsg sur une session Sway": {"en": "Requires swaymsg on a Sway session"},
    "Requiert swww sur Wayland": {"en": "Requires swww on Wayland"},
    "Requiert l'executable caelestia": {"en": "Requires the caelestia executable"},
    "Requiert feh sur X11": {"en": "Requires feh on X11"},
    "Requiert nitrogen sur X11": {"en": "Requires nitrogen on X11"},
    "Backend inconnu": {"en": "Unknown backend"},
    "Backend explicite '{backend_name}' actif.": {"en": "Explicit backend '{backend_name}' active."},
    "Backend '{backend_id}' indisponible ({reason}). Bascule automatique vers {backend_name}.": {
        "en": "Backend '{backend_id}' unavailable ({reason}). Automatic fallback to {backend_name}."
    },
    "Aucun backend wallpaper disponible pour '{backend_id}'.": {
        "en": "No wallpaper backend available for '{backend_id}'."
    },
    "Detection automatique: {backend_name}.": {"en": "Automatic detection: {backend_name}."},
    "Aucun backend wallpaper compatible detecte sur ce systeme.": {
        "en": "No compatible wallpaper backend detected on this system."
    },
    "Detection automatique: mpvpaper disponible pour wallpapers video sur Wayland/wlroots.": {
        "en": "Automatic detection: mpvpaper available for video wallpapers on Wayland/wlroots."
    },
    "Le support video requiert mpvpaper + mpv sur un compositeur wlroots compatible.": {
        "en": "Video support requires mpvpaper + mpv on a compatible wlroots compositor."
    },
    "Support video indisponible: {reasons}": {"en": "Video support unavailable: {reasons}"},
    "mpvpaper absent": {"en": "mpvpaper missing"},
    "mpv absent": {"en": "mpv missing"},
    "session non wlroots": {"en": "non-wlroots session"},
    "configuration inconnue": {"en": "unknown configuration"},
}


def _normalize_language(value: AppLanguage | str | None) -> AppLanguage:
    if isinstance(value, AppLanguage):
        return value
    try:
        return AppLanguage(str(value or AppLanguage.FR.value))
    except ValueError:
        return AppLanguage.FR


def set_language(value: AppLanguage | str | None) -> AppLanguage:
    global _CURRENT_LANGUAGE
    _CURRENT_LANGUAGE = _normalize_language(value)
    return _CURRENT_LANGUAGE


def current_language() -> AppLanguage:
    return _CURRENT_LANGUAGE


def tr(text: str, **kwargs) -> str:
    language = current_language().value
    translated = _TRANSLATIONS.get(text, {}).get(language, text)
    if kwargs:
        return translated.format(**kwargs)
    return translated


def language_label(language: AppLanguage | str) -> str:
    value = _normalize_language(language)
    return tr("Francais") if value is AppLanguage.FR else tr("Anglais")


def sort_field_label(value: SortField | str) -> str:
    mapping = {
        SortField.MTIME.value: "Date",
        SortField.NAME.value: "Nom",
        SortField.SIZE.value: "Taille",
        SortField.ORIENTATION.value: "Orientation",
        SortField.FAVORITE.value: "Favoris",
        SortField.RATING.value: "Note",
        SortField.VIEWS.value: "Vues",
        SortField.BRIGHTNESS.value: "Luminosite",
    }
    return tr(mapping.get(str(getattr(value, "value", value)), "Date"))


def theme_mode_label(value: ThemeMode | str) -> str:
    mapping = {
        ThemeMode.AUTO.value: "Auto (systeme)",
        ThemeMode.LIGHT.value: "Clair",
        ThemeMode.DARK.value: "Sombre",
    }
    return tr(mapping.get(str(getattr(value, "value", value)), "Auto (systeme)"))


def orientation_label(value: Orientation | str | None) -> str:
    mapping = {
        Orientation.LANDSCAPE.value: "Paysage",
        Orientation.PORTRAIT.value: "Portrait",
        Orientation.SQUARE.value: "Carre",
        Orientation.UNKNOWN.value: "Orientation",
    }
    raw = None if value is None else str(getattr(value, "value", value))
    if raw is None:
        return tr("Toutes orientations")
    return tr(mapping.get(raw, raw))


def media_kind_label(value: MediaKind | str | None) -> str:
    raw = None if value is None else str(getattr(value, "value", value))
    if raw == MediaKind.VIDEO.value:
        return tr("Video")
    return tr("Image")


def source_kind_label(value: WallpaperSourceKind | str | None) -> str:
    mapping = {
        WallpaperSourceKind.LOCAL.value: "Local",
        WallpaperSourceKind.WALLHAVEN.value: "Wallhaven",
        WallpaperSourceKind.MANUAL_IMPORT.value: "Import manuel",
        WallpaperSourceKind.GOWALL_GENERATED.value: "Gowall",
        WallpaperSourceKind.DERIVED_EDIT.value: "Derive",
    }
    raw = None if value is None else str(getattr(value, "value", value))
    if raw is None:
        return tr("Local")
    return tr(mapping.get(raw, raw))


def smart_collection_label(value: SmartCollection | str) -> str:
    mapping = {
        SmartCollection.FAVORITES.value: "Favoris",
        SmartCollection.VIDEOS.value: "Video wallpapers",
        SmartCollection.PORTRAITS.value: "Portraits",
        SmartCollection.LANDSCAPES.value: "Paysages",
        SmartCollection.SQUARES.value: "Carres",
        SmartCollection.NEVER_VIEWED.value: "Jamais vus",
        SmartCollection.TOP_RATED.value: "Notes 4-5",
        SmartCollection.DUPLICATES.value: "Doublons",
        SmartCollection.DARK.value: "Sombres",
        SmartCollection.ANIME.value: "Anime",
        SmartCollection.MINIMAL.value: "Minimal",
        SmartCollection.UNTAGGED.value: "Sans tags",
        SmartCollection.RECENT.value: "Recents",
        SmartCollection.INBOX.value: "Inbox",
    }
    return tr(mapping.get(str(getattr(value, "value", value)), str(value)))


def operation_label(value: str) -> str:
    return tr(value)


def yes_no(value: bool) -> str:
    return tr("Oui") if value else tr("Non")


def translate_qt_texts(root) -> None:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QCheckBox, QComboBox, QDockWidget, QGroupBox, QLabel, QLineEdit, QPushButton, QToolButton, QWidget

    widgets = [root] if isinstance(root, QWidget) else []
    if isinstance(root, QWidget):
        widgets.extend(root.findChildren(QWidget))
    for widget in widgets:
        if isinstance(widget, (QLabel, QPushButton, QToolButton, QCheckBox)):
            text = widget.text()
            if text:
                widget.setText(tr(text))
        if isinstance(widget, QLineEdit):
            placeholder = widget.placeholderText()
            if placeholder:
                widget.setPlaceholderText(tr(placeholder))
        if isinstance(widget, QComboBox):
            for index in range(widget.count()):
                widget.setItemText(index, tr(widget.itemText(index)))
        if isinstance(widget, QGroupBox):
            title = widget.title()
            if title:
                widget.setTitle(tr(title))
        if isinstance(widget, QDockWidget):
            title = widget.windowTitle()
            if title:
                widget.setWindowTitle(tr(title))
        title = widget.windowTitle()
        if title:
            widget.setWindowTitle(tr(title))
        tooltip = widget.toolTip()
        if tooltip:
            widget.setToolTip(tr(tooltip))
        status_tip = widget.statusTip()
        if status_tip:
            widget.setStatusTip(tr(status_tip))
    actions: list[QAction] = []
    if isinstance(root, QWidget):
        actions = root.findChildren(QAction)
    for action in actions:
        text = action.text()
        if text:
            action.setText(tr(text))
        tooltip = action.toolTip()
        if tooltip:
            action.setToolTip(tr(tooltip))
        status_tip = action.statusTip()
        if status_tip:
            action.setStatusTip(tr(status_tip))
