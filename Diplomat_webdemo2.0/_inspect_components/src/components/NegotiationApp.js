import { IconSprite } from './IconSprite.js';
import { Topbar } from './Topbar.js';
import { Topicbar } from './Topicbar.js';
import { StrategyPanel } from './StrategyPanel.js';
import { DialogueStage } from './DialogueStage.js';
import { SituationPanel } from './SituationPanel.js';
import { Modal } from './Modal.js';
import { Toast } from './Toast.js';
import { strategyCatalog, topic, initialSpeeches } from '../domain/negotiation.js';

export function NegotiationApp({ state, usedActionPoints, canEndTurn }) {
  return `${IconSprite()}<div class="grain" aria-hidden="true"></div><div class="app-shell">
    ${Topbar(state)}
    ${Topicbar({ topic, unreadEvents: state.eventRead ? 0 : 1 })}
    <main class="workspace" id="workspace">
      ${StrategyPanel({ strategies: strategyCatalog, selectedIds: state.selectedIds, used: usedActionPoints, total: state.actionPoints, canEndTurn })}
      ${DialogueStage({ speeches: initialSpeeches })}
      ${SituationPanel({ metrics: state.metrics })}
    </main>
  </div>${Modal()}${Toast()}`;
}
