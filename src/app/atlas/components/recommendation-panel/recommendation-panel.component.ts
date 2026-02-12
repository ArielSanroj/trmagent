/**
 * ATLAS Recommendation Panel Component
 * View and manage hedge recommendations
 */
import { Component, OnInit } from '@angular/core';
import {
  AtlasApiService,
  HedgeRecommendation
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-recommendation-panel',
  template: `
    <div class="recommendation-panel">
      <header class="page-header">
        <h1>Hedge Recommendations</h1>
        <button class="btn btn-primary" (click)="generateRecommendations()">
          Generate New
        </button>
      </header>

      <!-- Summary -->
      <section class="summary" *ngIf="summary">
        <div class="summary-item">
          <span class="count">{{ summary.pending_count }}</span>
          <span class="label">Pending</span>
        </div>
        <div class="summary-item">
          <span class="count">{{ summary.total_amount_to_hedge | number:'1.0-0' }}</span>
          <span class="label">USD to Hedge</span>
        </div>
        <div class="summary-item urgency-breakdown">
          <span class="urgency critical" *ngIf="summary.by_urgency?.critical">{{ summary.by_urgency.critical }} Critical</span>
          <span class="urgency high" *ngIf="summary.by_urgency?.high">{{ summary.by_urgency.high }} High</span>
          <span class="urgency normal" *ngIf="summary.by_urgency?.normal">{{ summary.by_urgency.normal }} Normal</span>
          <span class="urgency low" *ngIf="summary.by_urgency?.low">{{ summary.by_urgency.low }} Low</span>
        </div>
      </section>

      <!-- Filters -->
      <section class="filters">
        <select [(ngModel)]="filters.status" (change)="loadRecommendations()">
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="accepted">Accepted</option>
          <option value="rejected">Rejected</option>
          <option value="expired">Expired</option>
        </select>
        <select [(ngModel)]="filters.urgency" (change)="loadRecommendations()">
          <option value="">All Urgency</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>
        <select [(ngModel)]="filters.action" (change)="loadRecommendations()">
          <option value="">All Actions</option>
          <option value="hedge_now">Hedge Now</option>
          <option value="hedge_partial">Partial Hedge</option>
          <option value="wait">Wait</option>
          <option value="review">Review</option>
        </select>
      </section>

      <!-- Recommendations List -->
      <section class="recommendations-list">
        <div class="recommendation-card" *ngFor="let rec of recommendations"
             [class]="'urgency-' + rec.urgency + ' status-' + rec.status">
          <div class="rec-header">
            <span class="action-badge" [class]="rec.action">{{ formatAction(rec.action) }}</span>
            <span class="urgency-badge">{{ rec.urgency }}</span>
            <span class="status-badge">{{ rec.status }}</span>
          </div>

          <div class="rec-body">
            <div class="amount">
              <span class="currency">{{ rec.currency }}</span>
              <span class="value">{{ rec.amount_to_hedge | number:'1.0-0' }}</span>
            </div>

            <div class="details">
              <div class="detail">
                <span class="label">Days to Maturity</span>
                <span class="value">{{ rec.days_to_maturity }}</span>
              </div>
              <div class="detail">
                <span class="label">Current Coverage</span>
                <span class="value">{{ rec.current_coverage }}%</span>
              </div>
              <div class="detail">
                <span class="label">Target Coverage</span>
                <span class="value">{{ rec.target_coverage }}%</span>
              </div>
              <div class="detail" *ngIf="rec.confidence">
                <span class="label">Confidence</span>
                <span class="value">{{ rec.confidence }}%</span>
              </div>
            </div>

            <div class="reasoning" *ngIf="rec.reasoning">
              <strong>Reasoning:</strong> {{ rec.reasoning }}
            </div>

            <div class="valid-until" *ngIf="rec.valid_until && rec.status === 'pending'">
              Valid until: {{ rec.valid_until | date:'short' }}
            </div>
          </div>

          <div class="rec-actions" *ngIf="rec.status === 'pending'">
            <button class="btn btn-accept" (click)="accept(rec)">Accept & Create Order</button>
            <button class="btn btn-reject" (click)="showRejectModal(rec)">Reject</button>
          </div>

          <div class="rejection-info" *ngIf="rec.status === 'rejected' && rec.rejection_reason">
            <strong>Rejection reason:</strong> {{ rec.rejection_reason }}
          </div>
        </div>

        <div class="empty-state" *ngIf="recommendations.length === 0 && !loading">
          <p>No recommendations found. Generate new recommendations or adjust your filters.</p>
        </div>

        <div class="loading" *ngIf="loading">Loading recommendations...</div>
      </section>

      <!-- Reject Modal -->
      <div class="modal" *ngIf="showReject" (click)="closeRejectModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h3>Reject Recommendation</h3>
          <div class="form-group">
            <label>Reason (optional)</label>
            <textarea [(ngModel)]="rejectReason" rows="3" placeholder="Why are you rejecting this recommendation?"></textarea>
          </div>
          <div class="form-actions">
            <button class="btn btn-secondary" (click)="showReject = false">Cancel</button>
            <button class="btn btn-primary" (click)="confirmReject()">Reject</button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .recommendation-panel { padding: 20px; max-width: 1200px; margin: 0 auto; }
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .page-header h1 { margin: 0; }

    .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .btn-primary { background: #007bff; color: white; }
    .btn-accept { background: #28a745; color: white; }
    .btn-reject { background: #e9ecef; color: #333; }
    .btn-secondary { background: #6c757d; color: white; }

    .summary { display: flex; gap: 30px; background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .summary-item { display: flex; flex-direction: column; }
    .summary-item .count { font-size: 28px; font-weight: bold; color: #1a1a2e; }
    .summary-item .label { font-size: 12px; color: #666; }
    .urgency-breakdown { flex-direction: row; gap: 10px; align-items: center; }
    .urgency { padding: 4px 8px; border-radius: 4px; font-size: 11px; }
    .urgency.critical { background: #f8d7da; color: #721c24; }
    .urgency.high { background: #fff3cd; color: #856404; }
    .urgency.normal { background: #e2e3e5; color: #383d41; }
    .urgency.low { background: #d4edda; color: #155724; }

    .filters { display: flex; gap: 10px; margin-bottom: 20px; }
    .filters select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; }

    .recommendations-list { display: grid; gap: 15px; }

    .recommendation-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); border-left: 4px solid #6c757d; }
    .recommendation-card.urgency-critical { border-left-color: #dc3545; }
    .recommendation-card.urgency-high { border-left-color: #fd7e14; }
    .recommendation-card.urgency-normal { border-left-color: #ffc107; }
    .recommendation-card.urgency-low { border-left-color: #6c757d; }
    .recommendation-card.status-accepted { opacity: 0.7; }
    .recommendation-card.status-rejected { opacity: 0.5; }
    .recommendation-card.status-expired { opacity: 0.5; }

    .rec-header { display: flex; gap: 10px; margin-bottom: 15px; }
    .action-badge, .urgency-badge, .status-badge { padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
    .action-badge { background: #e9ecef; color: #333; }
    .action-badge.hedge_now { background: #f8d7da; color: #721c24; }
    .action-badge.hedge_partial { background: #fff3cd; color: #856404; }
    .action-badge.wait { background: #d1ecf1; color: #0c5460; }
    .action-badge.review { background: #e2e3e5; color: #383d41; }
    .urgency-badge { background: #f8f9fa; color: #666; }
    .status-badge { background: #f8f9fa; color: #666; }

    .rec-body .amount { margin-bottom: 15px; }
    .rec-body .amount .currency { font-size: 14px; color: #666; margin-right: 5px; }
    .rec-body .amount .value { font-size: 32px; font-weight: bold; color: #1a1a2e; }

    .details { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px; margin-bottom: 15px; }
    .detail { display: flex; flex-direction: column; }
    .detail .label { font-size: 11px; color: #666; }
    .detail .value { font-size: 16px; font-weight: 600; }

    .reasoning { font-size: 14px; color: #666; line-height: 1.5; margin-bottom: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px; }
    .valid-until { font-size: 12px; color: #999; }

    .rec-actions { display: flex; gap: 10px; margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee; }
    .rejection-info { margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 4px; font-size: 13px; }

    .empty-state, .loading { text-align: center; padding: 40px; color: #666; }

    .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal-content { background: white; border-radius: 8px; padding: 30px; width: 100%; max-width: 400px; }
    .modal-content h3 { margin: 0 0 20px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: 500; }
    .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    .form-actions { display: flex; justify-content: flex-end; gap: 10px; }
  `]
})
export class RecommendationPanelComponent implements OnInit {
  recommendations: HedgeRecommendation[] = [];
  summary: any = null;
  loading = false;

  filters = {
    status: '',
    urgency: '',
    action: ''
  };

  showReject = false;
  rejectingRec: HedgeRecommendation | null = null;
  rejectReason = '';

  constructor(private atlasApi: AtlasApiService) {}

  ngOnInit() {
    this.loadRecommendations();
    this.loadSummary();
  }

  loadRecommendations() {
    this.loading = true;
    const params: any = {};
    if (this.filters.status) params.status = this.filters.status;
    if (this.filters.urgency) params.urgency = this.filters.urgency;
    if (this.filters.action) params.action = this.filters.action;

    this.atlasApi.getRecommendations(params).subscribe({
      next: (data) => {
        this.recommendations = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading recommendations:', err);
        this.loading = false;
      }
    });
  }

  loadSummary() {
    this.atlasApi.getRecommendationsSummary().subscribe({
      next: (data) => this.summary = data,
      error: (err) => console.error('Error loading summary:', err)
    });
  }

  generateRecommendations() {
    this.atlasApi.generateRecommendations().subscribe({
      next: () => {
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error generating recommendations:', err)
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

  accept(rec: HedgeRecommendation) {
    this.atlasApi.createOrderFromRecommendation(rec.id).subscribe({
      next: () => {
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error accepting recommendation:', err)
    });
  }

  showRejectModal(rec: HedgeRecommendation) {
    this.rejectingRec = rec;
    this.rejectReason = '';
    this.showReject = true;
  }

  confirmReject() {
    if (!this.rejectingRec) return;

    this.atlasApi.rejectRecommendation(this.rejectingRec.id, this.rejectReason).subscribe({
      next: () => {
        this.showReject = false;
        this.rejectingRec = null;
        this.loadRecommendations();
        this.loadSummary();
      },
      error: (err) => console.error('Error rejecting recommendation:', err)
    });
  }

  closeRejectModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showReject = false;
    }
  }
}
