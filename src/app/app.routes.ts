import { Routes } from '@angular/router';
import { DashboardComponent } from './dashboard/dashboard.component';
import { PredictionsComponent } from './predictions/predictions.component';
import { BacktestingComponent } from './backtesting/backtesting.component';
import { AgentChatComponent } from './agent-chat/agent-chat.component';

export const routes: Routes = [
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: 'dashboard', component: DashboardComponent },
  { path: 'predictions', component: PredictionsComponent },
  { path: 'backtesting', component: BacktestingComponent },
  { path: 'chat', component: AgentChatComponent },
  { path: '**', redirectTo: '/dashboard' }
];
