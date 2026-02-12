/**
 * ATLAS Module - Treasury Copilot for FX Risk Management
 */
import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, Routes } from '@angular/router';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

// Components
import { CoverageDashboardComponent } from './components/coverage-dashboard/coverage-dashboard.component';
import { ExposureManagerComponent } from './components/exposure-manager/exposure-manager.component';
import { PolicyEditorComponent } from './components/policy-editor/policy-editor.component';
import { RecommendationPanelComponent } from './components/recommendation-panel/recommendation-panel.component';
import { ExecutionConsoleComponent } from './components/execution-console/execution-console.component';

// Services
import { AtlasApiService } from './services/atlas-api.service';

const routes: Routes = [
  {
    path: '',
    component: CoverageDashboardComponent
  },
  {
    path: 'exposures',
    component: ExposureManagerComponent
  },
  {
    path: 'policies',
    component: PolicyEditorComponent
  },
  {
    path: 'recommendations',
    component: RecommendationPanelComponent
  },
  {
    path: 'execution',
    component: ExecutionConsoleComponent
  }
];

@NgModule({
  declarations: [
    CoverageDashboardComponent,
    ExposureManagerComponent,
    PolicyEditorComponent,
    RecommendationPanelComponent,
    ExecutionConsoleComponent
  ],
  imports: [
    CommonModule,
    FormsModule,
    ReactiveFormsModule,
    HttpClientModule,
    RouterModule.forChild(routes)
  ],
  providers: [
    AtlasApiService
  ],
  exports: [
    CoverageDashboardComponent
  ]
})
export class AtlasModule { }
