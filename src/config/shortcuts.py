from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ShortcutDefinition:
    action_id: str
    label: str
    default_sequence: str
    description: str


SHORTCUT_DEFINITIONS: tuple[ShortcutDefinition, ...] = (
    ShortcutDefinition("find", "Recherche", "Ctrl+F", "Placer le focus dans la recherche"),
    ShortcutDefinition("scan", "Scanner", "F5", "Relancer l'indexation de la bibliotheque"),
    ShortcutDefinition("scan_inbox", "Importer Inbox", "Ctrl+I", "Importer les images du dossier Inbox"),
    ShortcutDefinition("grid", "Vue grille", "G", "Afficher la grille"),
    ShortcutDefinition("viewer", "Visionneuse", "V", "Ouvrir l'image courante dans la visionneuse"),
    ShortcutDefinition("favorite", "Favori", "F", "Basculer le favori sur la selection"),
    ShortcutDefinition("move", "Deplacer", "M", "Deplacer les wallpapers selectionnes"),
    ShortcutDefinition("rename", "Renommer", "R", "Renommer les wallpapers selectionnes"),
    ShortcutDefinition("delete", "Corbeille", "Delete", "Envoyer la selection vers la corbeille"),
    ShortcutDefinition("open_folder", "Ouvrir dossier", "O", "Ouvrir le dossier du wallpaper courant"),
    ShortcutDefinition("quick_tag", "Tag rapide", "T", "Modifier rapidement les tags du wallpaper courant"),
    ShortcutDefinition("previous_item", "Precedent", "K", "Selectionner ou afficher le wallpaper precedent"),
    ShortcutDefinition("next_item", "Suivant", "J", "Selectionner ou afficher le wallpaper suivant"),
    ShortcutDefinition("apply", "Appliquer", "A", "Appliquer le wallpaper courant"),
    ShortcutDefinition("random_apply", "Appliquer aleatoire", "Ctrl+W", "Choisir un wallpaper aleatoire dans le filtre courant"),
    ShortcutDefinition("review_inbox", "Review Inbox", "Ctrl+Shift+I", "Ouvrir le filtre Inbox et la visionneuse"),
    ShortcutDefinition("review_duplicates", "Review doublons", "Ctrl+Shift+D", "Ouvrir la revue des doublons"),
    ShortcutDefinition("rating_1", "Note 1", "1", "Attribuer la note 1 au wallpaper courant"),
    ShortcutDefinition("rating_2", "Note 2", "2", "Attribuer la note 2 au wallpaper courant"),
    ShortcutDefinition("rating_3", "Note 3", "3", "Attribuer la note 3 au wallpaper courant"),
    ShortcutDefinition("rating_4", "Note 4", "4", "Attribuer la note 4 au wallpaper courant"),
    ShortcutDefinition("rating_5", "Note 5", "5", "Attribuer la note 5 au wallpaper courant"),
    ShortcutDefinition("duplicates", "Calcul doublons", "Ctrl+D", "Calculer les hash manquants et mettre a jour les doublons"),
    ShortcutDefinition("slideshow", "Slideshow", "S", "Activer ou couper le slideshow"),
    ShortcutDefinition("history", "Historique", "H", "Ouvrir l'historique des operations"),
    ShortcutDefinition("settings", "Parametres", "Ctrl+,", "Ouvrir les parametres"),
    ShortcutDefinition("shortcuts_help", "Aide raccourcis", "?", "Afficher la liste des raccourcis"),
)


def default_shortcut_map() -> dict[str, str]:
    return {definition.action_id: definition.default_sequence for definition in SHORTCUT_DEFINITIONS}
