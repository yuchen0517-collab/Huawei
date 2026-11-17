import { IconSprite } from './IconSprite.js';
import { Topbar } from './Topbar.js';
import { StrategyPanel } from './StrategyPanel.js';
import { DialogueStage, ReportFab } from './DialogueStage.js';
import { SituationPanel } from './SituationPanel.js';
import { Modal } from './Modal.js';
import { TreeDrawer } from './Drawer.js';
import { Toast } from './Toast.js';
import { strategyCatalog, topic, initialSpeeches } from '../domain/negotiation.js';

export function NegotiationApp({ state, usedActionPoints, canEndTurn, baseActions = [] }) {
  return `${IconSprite()}<div class="stage-bg" aria-hidden="true"><div class="stage-bg-blur"></div><div class="stage-bg-photo"></div></div><div class="grain" aria-hidden="true"></div><div class="app-shell">
    ${Topbar({ round: state.round, maxRounds: state.maxRounds, unreadEvents: state.eventRead ? 0 : 1 })}
    <main class="workspace" id="workspace">
      ${StrategyPanel({ strategies: strategyCatalog, selectedIds: state.selectedIds, used: usedActionPoints, total: state.actionPoints, canEndTurn, version: state.version, phase: state.phase, coach: state.coach, coachStatus: state.coachStatus, coachCollapsed: state.coachCollapsed, baseActions })}
      ${DialogueStage({ speeches: initialSpeeches, topic })}
      ${SituationPanel({ metrics: state.metrics })}
    </main>
  </div>${TreeDrawer({ topic, round: state.round, nodeCount: (state.log || []).length + 1 })}${ReportFab()}${Modal()}${Toast()}`;
}