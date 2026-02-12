/**
 * ATLAS Coverage Dashboard Component
 * Main dashboard showing FX exposure coverage status
 */
import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject, interval } from 'rxjs';
import { takeUntil, switchMap, startWith } from 'rxjs/operators';
import {
  AtlasApiService,
  DashboardSummary,
  ExposureSummary,
  MaturityLadder,
  HedgeRecommendation
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-coverage-dashboard',
  template: `
    <div class="atlas-dashboard">
      <header class="dashboard-header">
        <h1>ATLAS - Treasury Copilot</h1>
        <p class="subtitle">FX Risk Management Dashboard</p>
        <span class="last-update" *ngIf="lastUpdate">
          Last updated: {{ lastUpdate | date:'medium' }}
        </span>
      </header>

      <!-- Key Metrics -->
      <section class="metrics-grid" *ngIf="dashboard">
        <div class="metric-card">
          <h3>Net Exposure</h3>
          <div class="metric-value" [class.positive]="dashboard.coverage.net_exposure > 0" [class.negative]="dashboard.coverage.net_exposure < 0">
            {{ dashboard.currency }} {{ dashboard.coverage.net_exposure | number:'1.0-0' }}
          </div>
          <span class="metric-label">Total FX exposure</span>
        </div>

        <div class="metric-card">
          <h3>Coverage</h3>
          <div class="metric-value coverage" [class.good]="dashboard.coverage.overall_coverage_pct >= 70" [class.warning]="dashboard.coverage.overall_coverage_pct >= 40 && dashboard.coverage.overall_coverage_pct < 70" [class.bad]="dashboard.coverage.overall_coverage_pct < 40">
            {{ dashboard.coverage.overall_coverage_pct | number:'1.1-1' }}%
          </div>
          <span class="metric-label">Overall hedge ratio</span>
        </div>

        <div class="metric-card">
          <h3>Payables Coverage</h3>
          <div class="metric-value">
            {{ dashboard.coverage.payables_coverage_pct | number:'1.1-1' }}%
          </div>
          <span class="metric-label">Accounts payable hedged</span>
        </div>

        <div class="metric-card">
          <h3>Receivables Coverage</h3>
          <div class="metric-value">
            {{ dashboard.coverage.receivables_coverage_pct | number:'1.1-1' }}%
          </div>
          <span class="metric-label">Accounts receivable hedged</span>
        </div>
      </section>

      <!-- Exposure Summary by Horizon -->
      <section class="horizon-section" *ngIf="exposureSummary">
        <h2>Exposure by Time Horizon</h2>
        <div class="horizon-grid">
          <div class="horizon-card" *ngFor="let horizon of horizons">
            <h4>{{ horizon.label }}</h4>
            <div class="horizon-stats" *ngIf="exposureSummary.by_horizon[horizon.key] as h">
              <div class="stat">
                <span class="stat-label">Total</span>
                <span class="stat-value">{{ h.total | number:'1.0-0' }}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Open</span>
                <span class="stat-value">{{ h.open | number:'1.0-0' }}</span>
              </div>
              <div class="stat">
                <span class="stat-label">Coverage</span>
                <span class="stat-value" [class.good]="h.coverage_pct >= 70">{{ h.coverage_pct | number:'1.1-1' }}%</span>
              </div>
              <div class="coverage-bar">
                <div class="coverage-fill" [style.width.%]="h.coverage_pct"></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Pending Recommendations -->
      <section class="recommendations-section" *ngIf="pendingRecommendations.length > 0">
        <h2>Pending Recommendations</h2>
        <div class="recommendations-list">
          <div class="recommendation-card" *ngFor="let rec of pendingRecommendations" [class]="'urgency-' + rec.urgency">
            <div class="rec-header">
              <span class="rec-action" [class]="'action-' + rec.action">{{ formatAction(rec.action) }}</span>
              <span class="rec-urgency">{{ rec.urgency }}</span>
            </div>
            <div class="rec-body">
              <div class="rec-amount">{{ rec.currency }} {{ rec.amount_to_hedge | number:'1.0-0' }}</div>
              <div class="rec-details">
                <span>Days to maturity: {{ rec.days_to_maturity }}</span>
                <span>Target coverage: {{ rec.target_coverage }}%</span>
              </div>
            </div>
            <div class="rec-actions">
              <button class="btn btn-accept" (click)="acceptRecommendation(rec)">Accept</button>
              <button class="btn btn-reject" (click)="rejectRecommendation(rec)">Reject</button>
            </div>
          </div>
        </div>
        <a routerLink="/atlas/recommendations" class="view-all">View all recommendations</a>
      </section>

      <!-- Maturity Ladder Preview -->
      <section class="maturity-section" *ngIf="maturityLadder">
        <h2>Maturity Ladder (Next 8 Weeks)</h2>
        <div class="maturity-chart">
          <div class="maturity-bar" *ngFor="let bucket of maturityLadder.buckets.slice(0, 8)">
            <div class="bar-container">
              <div class="bar-total" [style.height.%]="getBarHeight(bucket.total)"></div>
              <div class="bar-hedged" [style.height.%]="getBarHeight(bucket.hedged)"></div>
            </div>
            <span class="bar-label">{{ formatBucketDate(bucket.start_date) }}</span>
          </div>
        </div>
        <div class="maturity-legend">
          <span class="legend-item"><span class="legend-color total"></span> Total Exposure</span>
          <span class="legend-item"><span class="legend-color hedged"></span> Hedged</span>
        </div>
      </section>

      <!-- Quick Actions -->
      <section class="quick-actions">
        <h2>Quick Actions</h2>
        <div class="action-buttons">
          <a routerLink="/atlas/exposures" class="action-btn">
            <span class="action-icon">+</span>
            Manage Exposures
          </a>
          <a routerLink="/atlas/policies" class="action-btn">
            <span class="action-icon">*</span>
            Configure Policies
          </a>
          <a routerLink="/atlas/recommendations" class="action-btn">
            <span class="action-icon">!</span>
            Review Recommendations
          </a>
          <a routerLink="/atlas/execution" class="action-btn">
            <span class="action-icon">></span>
            Execution Console
          </a>
        </div>
      </section>

      <div class="loading-overlay" *ngIf="loading">
        <div class="spinner"></div>
        <span>Loading dashboard...</span>
      </div>
    </div>
  `,
  styles: [`
    .atlas-dashboard {
      padding: 20px;
      max-width: 1400px;
      margin: 0 auto;
    }

    .dashboard-header {
      margin-bottom: 30px;
    }

    .dashboard-header h1 {
      margin: 0;
      font-size: 28px;
      color: #1a1a2e;
    }

    .subtitle {
      color: #666;
      margin: 5px 0;
    }

    .last-update {
      font-size: 12px;
      color: #999;
    }

    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 20px;
      margin-bottom: 30px;
    }

    .metric-card {
      background: white;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .metric-card h3 {
      margin: 0 0 10px;
      font-size: 14px;
      color: #666;
      text-transform: uppercase;
    }

    .metric-value {
      font-size: 32px;
      font-weight: bold;
      color: #1a1a2e;
    }

    .metric-value.positive { color: #28a745; }
    .metric-value.negative { color: #dc3545; }
    .metric-value.good { color: #28a745; }
    .metric-value.warning { color: #ffc107; }
    .metric-value.bad { color: #dc3545; }

    .metric-label {
      font-size: 12px;
      color: #999;
    }

    .horizon-section, .recommendations-section, .maturity-section, .quick-actions {
      background: white;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }

    .horizon-section h2, .recommendations-section h2, .maturity-section h2, .quick-actions h2 {
      margin: 0 0 20px;
      font-size: 18px;
      color: #1a1a2e;
    }

    .horizon-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 15px;
    }

    .horizon-card {
      background: #f8f9fa;
      border-radius: 6px;
      padding: 15px;
    }

    .horizon-card h4 {
      margin: 0 0 10px;
      font-size: 14px;
      color: #333;
    }

    .stat {
      display: flex;
      justify-content: space-between;
      margin-bottom: 5px;
      font-size: 13px;
    }

    .stat-label { color: #666; }
    .stat-value { font-weight: 600; }
    .stat-value.good { color: #28a745; }

    .coverage-bar {
      height: 6px;
      background: #e9ecef;
      border-radius: 3px;
      margin-top: 10px;
      overflow: hidden;
    }

    .coverage-fill {
      height: 100%;
      background: #28a745;
      transition: width 0.3s ease;
    }

    .recommendations-list {
      display: grid;
      gap: 15px;
    }

    .recommendation-card {
      border: 1px solid #e9ecef;
      border-radius: 6px;
      padding: 15px;
      border-left: 4px solid #6c757d;
    }

    .recommendation-card.urgency-critical { border-left-color: #dc3545; }
    .recommendation-card.urgency-high { border-left-color: #fd7e14; }
    .recommendation-card.urgency-normal { border-left-color: #ffc107; }
    .recommendation-card.urgency-low { border-left-color: #6c757d; }

    .rec-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 10px;
    }

    .rec-action {
      font-weight: 600;
      text-transform: uppercase;
      font-size: 12px;
    }

    .rec-action.action-hedge_now { color: #dc3545; }
    .rec-action.action-hedge_partial { color: #fd7e14; }
    .rec-action.action-wait { color: #17a2b8; }
    .rec-action.action-review { color: #6c757d; }

    .rec-urgency {
      font-size: 12px;
      color: #666;
      text-transform: capitalize;
    }

    .rec-amount {
      font-size: 24px;
      font-weight: bold;
      color: #1a1a2e;
    }

    .rec-details {
      display: flex;
      gap: 20px;
      font-size: 13px;
      color: #666;
      margin-top: 5px;
    }

    .rec-actions {
      margin-top: 15px;
      display: flex;
      gap: 10px;
    }

    .btn {
      padding: 8px 16px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 13px;
      transition: background 0.2s;
    }

    .btn-accept {
      background: #28a745;
      color: white;
    }

    .btn-accept:hover { background: #218838; }

    .btn-reject {
      background: #e9ecef;
      color: #333;
    }

    .btn-reject:hover { background: #dee2e6; }

    .view-all {
      display: block;
      text-align: center;
      margin-top: 15px;
      color: #007bff;
      text-decoration: none;
    }

    .view-all:hover { text-decoration: underline; }

    .maturity-chart {
      display: flex;
      align-items: flex-end;
      height: 200px;
      gap: 10px;
      padding: 20px 0;
    }

    .maturity-bar {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
    }

    .bar-container {
      width: 100%;
      height: 150px;
      position: relative;
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
    }

    .bar-total {
      width: 100%;
      background: #e9ecef;
      position: absolute;
      bottom: 0;
    }

    .bar-hedged {
      width: 100%;
      background: #28a745;
      position: absolute;
      bottom: 0;
    }

    .bar-label {
      font-size: 11px;
      color: #666;
      margin-top: 5px;
    }

    .maturity-legend {
      display: flex;
      justify-content: center;
      gap: 20px;
      margin-top: 10px;
    }

    .legend-item {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      color: #666;
    }

    .legend-color {
      width: 12px;
      height: 12px;
      border-radius: 2px;
    }

    .legend-color.total { background: #e9ecef; }
    .legend-color.hedged { background: #28a745; }

    .action-buttons {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 15px;
    }

    .action-btn {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 15px 20px;
      background: #f8f9fa;
      border-radius: 6px;
      text-decoration: none;
      color: #333;
      transition: background 0.2s;
    }

    .action-btn:hover {
      background: #e9ecef;
    }

    .action-icon {
      width: 32px;
      height: 32px;
      background: #007bff;
      color: white;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
    }

    .loading-overlay {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(255,255,255,0.9);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }

    .spinner {
      width: 40px;
      height: 40px;
      border: 3px solid #e9ecef;
      border-top-color: #007bff;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `]
})
export class CoverageDashboardComponent implements OnInit, OnDestroy {
  private destroy$ = new Subject<void>();

  dashboard: DashboardSummary | null = null;
  exposureSummary: ExposureSummary | null = null;
  maturityLadder: MaturityLadder | null = null;
  pendingRecommendations: HedgeRecommendation[] = [];

  loading = true;
  lastUpdate: Date | null = null;
  maxBarValue = 0;

  horizons = [
    { key: '0-30', label: '0-30 Days' },
    { key: '31-60', label: '31-60 Days' },
    { key: '61-90', label: '61-90 Days' },
    { key: '91+', label: '91+ Days' }
  ];

  constructor(private atlasApi: AtlasApiService) {}

  ngOnInit() {
    this.loadDashboard();

    // Refresh every 5 minutes
    interval(5 * 60 * 1000)
      .pipe(
        takeUntil(this.destroy$),
        startWith(0)
      )
      .subscribe(() => this.loadDashboard());
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }

  loadDashboard() {
    this.loading = true;

    // Load all data in parallel
    Promise.all([
      this.atlasApi.getDashboard().toPromise(),
      this.atlasApi.getExposureSummary().toPromise(),
      this.atlasApi.getMaturityLadder('USD', 7).toPromise(),
      this.atlasApi.getPendingRecommendations().toPromise()
    ]).then(([dashboard, summary, ladder, recommendations]) => {
      this.dashboard = dashboard || null;
      this.exposureSummary = summary || null;
      this.maturityLadder = ladder || null;
      this.pendingRecommendations = (recommendations || []).slice(0, 5);

      if (ladder && ladder.buckets.length > 0) {
        this.maxBarValue = Math.max(...ladder.buckets.map(b => b.total));
      }

      this.lastUpdate = new Date();
      this.loading = false;
    }).catch(error => {
      console.error('Error loading dashboard:', error);
      this.loading = false;
    });
  }

  formatAction(action: string): string {
    const actions: { [key: string]: string } = {
      'hedge_now': 'Hedge Now',
      'hedge_partial': 'Partial Hedge',
      'wait': 'Wait',
      'review': 'Review'
    };
    return actions[action] || action;
  }

  formatBucketDate(dateStr: string): string {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  }

  getBarHeight(value: number): number {
    if (this.maxBarValue === 0) return 0;
    return (value / this.maxBarValue) * 100;
  }

  acceptRecommendation(rec: HedgeRecommendation) {
    this.atlasApi.acceptRecommendation(rec.id).subscribe({
      next: () => {
        this.pendingRecommendations = this.pendingRecommendations.filter(r => r.id !== rec.id);
      },
      error: (err) => console.error('Error accepting recommendation:', err)
    });
  }

  rejectRecommendation(rec: HedgeRecommendation) {
    this.atlasApi.rejectRecommendation(rec.id).subscribe({
      next: () => {
        this.pendingRecommendations = this.pendingRecommendations.filter(r => r.id !== rec.id);
      },
      error: (err) => console.error('Error rejecting recommendation:', err)
    });
  }
}
