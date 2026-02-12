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
  templateUrl: './coverage-dashboard.component.html',
  styleUrls: ['./coverage-dashboard.component.scss'],
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
