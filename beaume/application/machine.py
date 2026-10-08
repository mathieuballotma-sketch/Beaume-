"""Machine a etats d'un document. Empeche les transitions illegales."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from beaume.application.etats import EtatDocument, TRANSITIONS


class TransitionIllegale(Exception):
    pass


@dataclass
class Document:
    chemin: Path
    etat: EtatDocument = EtatDocument.DEPOSE
    historique: list[tuple[datetime, EtatDocument, str]] = field(
        default_factory=list
    )

    def transition(self, nouvel_etat: EtatDocument, raison: str = "") -> None:
        autorisees = TRANSITIONS[self.etat]
        if nouvel_etat not in autorisees:
            raise TransitionIllegale(
                f"Transition interdite : {self.etat.value} -> "
                f"{nouvel_etat.value}"
            )
        maintenant = datetime.now(timezone.utc)
        self.historique.append((maintenant, self.etat, raison))
        self.etat = nouvel_etat
        self.historique.append((maintenant, nouvel_etat, raison))

    def echouer(self, raison: str) -> None:
        self.transition(EtatDocument.ECHEC, raison)
