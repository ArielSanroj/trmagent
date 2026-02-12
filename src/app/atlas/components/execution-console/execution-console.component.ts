/**
 * ATLAS Execution Console Component
 * Manage hedge orders and execution workflow
 */
import { Component, OnInit } from '@angular/core';
import {
  AtlasApiService,
  HedgeOrder,
  Quote
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-execution-console',
  template: `
    <div class="execution-console">
      <header class="page-header">
        <h1>Execution Console</h1>
      </header>

      <!-- Summary -->
      <section class="summary" *ngIf="orderSummary">
        <div class="summary-card">
          <span class="count">{{ orderSummary.by_status?.pending_approval || 0 }}</span>
          <span class="label">Pending Approval</span>
        </div>
        <div class="summary-card">
          <span class="count">{{ orderSummary.pending_approval_amount | number:'1.0-0' }}</span>
          <span class="label">USD Pending</span>
        </div>
        <div class="summary-card">
          <span class="count">{{ orderSummary.by_status?.approved || 0 }}</span>
          <span class="label">Ready to Execute</span>
        </div>
        <div class="summary-card">
          <span class="count">{{ orderSummary.executed_today || 0 }}</span>
          <span class="label">Executed Today</span>
        </div>
      </section>

      <!-- Filters -->
      <section class="filters">
        <select [(ngModel)]="filters.status" (change)="loadOrders()">
          <option value="">All Statuses</option>
          <option value="pending_approval">Pending Approval</option>
          <option value="approved">Approved</option>
          <option value="quoted">Quoted</option>
          <option value="executed">Executed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </section>

      <!-- Orders List -->
      <section class="orders-list">
        <div class="order-card" *ngFor="let order of orders" [class]="'status-' + order.status">
          <div class="order-header">
            <span class="order-ref">{{ order.internal_reference }}</span>
            <span class="status-badge" [class]="order.status">{{ formatStatus(order.status) }}</span>
          </div>

          <div class="order-body">
            <div class="order-main">
              <span class="side" [class]="order.side">{{ order.side.toUpperCase() }}</span>
              <span class="amount">{{ order.currency }} {{ order.amount | number:'1.0-0' }}</span>
              <span class="type">{{ order.order_type }}</span>
            </div>

            <div class="order-details">
              <div class="detail" *ngIf="order.target_rate">
                <span class="label">Target Rate</span>
                <span class="value">{{ order.target_rate | number:'1.4-4' }}</span>
              </div>
              <div class="detail" *ngIf="order.market_rate_at_creation">
                <span class="label">Market Rate (at creation)</span>
                <span class="value">{{ order.market_rate_at_creation | number:'1.4-4' }}</span>
              </div>
              <div class="detail" *ngIf="order.settlement_date">
                <span class="label">Settlement Date</span>
                <span class="value">{{ order.settlement_date | date:'mediumDate' }}</span>
              </div>
              <div class="detail">
                <span class="label">Created</span>
                <span class="value">{{ order.created_at | date:'short' }}</span>
              </div>
            </div>

            <div class="order-notes" *ngIf="order.notes">
              <strong>Notes:</strong> {{ order.notes }}
            </div>
          </div>

          <div class="order-actions">
            <!-- Pending Approval -->
            <ng-container *ngIf="order.status === 'pending_approval'">
              <button class="btn btn-success" (click)="approveOrder(order)">Approve</button>
              <button class="btn btn-secondary" (click)="rejectOrder(order)">Reject</button>
            </ng-container>

            <!-- Approved - Ready to get quotes -->
            <ng-container *ngIf="order.status === 'approved'">
              <button class="btn btn-primary" (click)="showQuoteModal(order)">Add Quote</button>
              <button class="btn btn-secondary" (click)="cancelOrder(order)">Cancel</button>
            </ng-container>

            <!-- Quoted - Ready to execute -->
            <ng-container *ngIf="order.status === 'quoted'">
              <button class="btn btn-success" (click)="showExecuteModal(order)">Execute</button>
              <button class="btn btn-secondary" (click)="cancelOrder(order)">Cancel</button>
            </ng-container>

            <!-- Executed -->
            <ng-container *ngIf="order.status === 'executed'">
              <span class="executed-info">
                Executed at {{ order.executed_at | date:'short' }}
                <span *ngIf="order.bank_reference">| Ref: {{ order.bank_reference }}</span>
              </span>
            </ng-container>
          </div>
        </div>

        <div class="empty-state" *ngIf="orders.length === 0 && !loading">
          <p>No orders found. Orders are created from accepted recommendations.</p>
        </div>

        <div class="loading" *ngIf="loading">Loading orders...</div>
      </section>

      <!-- Add Quote Modal -->
      <div class="modal" *ngIf="showQuote" (click)="closeQuoteModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h3>Add Quote for {{ selectedOrder?.internal_reference }}</h3>
          <form (ngSubmit)="submitQuote()">
            <div class="form-group">
              <label>Provider/Bank *</label>
              <input type="text" [(ngModel)]="quoteData.provider" name="provider" placeholder="e.g., Bancolombia">
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Bid Rate</label>
                <input type="number" [(ngModel)]="quoteData.bid_rate" name="bid_rate" step="0.0001">
              </div>
              <div class="form-group">
                <label>Ask Rate</label>
                <input type="number" [(ngModel)]="quoteData.ask_rate" name="ask_rate" step="0.0001">
              </div>
            </div>
            <div class="form-group">
              <label>Provider Reference</label>
              <input type="text" [(ngModel)]="quoteData.provider_reference" name="provider_reference">
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" (click)="showQuote = false">Cancel</button>
              <button type="submit" class="btn btn-primary" [disabled]="!quoteData.provider">Add Quote</button>
            </div>
          </form>
        </div>
      </div>

      <!-- Execute Modal -->
      <div class="modal" *ngIf="showExecute" (click)="closeExecuteModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h3>Execute Order {{ selectedOrder?.internal_reference }}</h3>
          <form (ngSubmit)="submitExecution()">
            <div class="form-row">
              <div class="form-group">
                <label>Executed Rate *</label>
                <input type="number" [(ngModel)]="executeData.executed_rate" name="executed_rate" step="0.0001" required>
              </div>
              <div class="form-group">
                <label>Bank Reference</label>
                <input type="text" [(ngModel)]="executeData.bank_reference" name="bank_reference">
              </div>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Trade Date *</label>
                <input type="date" [(ngModel)]="executeData.trade_date" name="trade_date" required>
              </div>
              <div class="form-group">
                <label>Value Date *</label>
                <input type="date" [(ngModel)]="executeData.value_date" name="value_date" required>
              </div>
            </div>
            <div class="form-group">
              <label>Counterparty Bank</label>
              <input type="text" [(ngModel)]="executeData.counterparty_bank" name="counterparty_bank">
            </div>
            <div class="form-actions">
              <button type="button" class="btn btn-secondary" (click)="showExecute = false">Cancel</button>
              <button type="submit" class="btn btn-success">Confirm Execution</button>
            </div>
          </form>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .execution-console { padding: 20px; max-width: 1200px; margin: 0 auto; }
    .page-header { margin-bottom: 20px; }
    .page-header h1 { margin: 0; }

    .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
    .btn-primary { background: #007bff; color: white; }
    .btn-success { background: #28a745; color: white; }
    .btn-secondary { background: #6c757d; color: white; }

    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
    .summary-card { background: white; border-radius: 8px; padding: 20px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .summary-card .count { display: block; font-size: 28px; font-weight: bold; color: #1a1a2e; }
    .summary-card .label { font-size: 12px; color: #666; }

    .filters { margin-bottom: 20px; }
    .filters select { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; }

    .orders-list { display: grid; gap: 15px; }

    .order-card { background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .order-card.status-executed { opacity: 0.8; }
    .order-card.status-cancelled { opacity: 0.5; }

    .order-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }
    .order-ref { font-weight: 600; color: #333; }
    .status-badge { padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .status-badge.pending_approval { background: #fff3cd; color: #856404; }
    .status-badge.approved { background: #d1ecf1; color: #0c5460; }
    .status-badge.quoted { background: #d4edda; color: #155724; }
    .status-badge.executed { background: #28a745; color: white; }
    .status-badge.cancelled { background: #f8d7da; color: #721c24; }

    .order-main { display: flex; align-items: center; gap: 15px; margin-bottom: 15px; }
    .side { padding: 4px 12px; border-radius: 4px; font-weight: 600; font-size: 12px; }
    .side.buy { background: #d4edda; color: #155724; }
    .side.sell { background: #f8d7da; color: #721c24; }
    .amount { font-size: 28px; font-weight: bold; color: #1a1a2e; }
    .type { color: #666; font-size: 14px; }

    .order-details { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 15px; }
    .detail .label { display: block; font-size: 11px; color: #666; }
    .detail .value { font-size: 14px; font-weight: 600; }

    .order-notes { font-size: 13px; color: #666; padding: 10px; background: #f8f9fa; border-radius: 4px; margin-bottom: 15px; }

    .order-actions { display: flex; gap: 10px; padding-top: 15px; border-top: 1px solid #eee; }
    .executed-info { font-size: 13px; color: #666; }

    .empty-state, .loading { text-align: center; padding: 40px; color: #666; }

    .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal-content { background: white; border-radius: 8px; padding: 30px; width: 100%; max-width: 500px; }
    .modal-content h3 { margin: 0 0 20px; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px; }
    .form-group input { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
    .form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
  `]
})
export class ExecutionConsoleComponent implements OnInit {
  orders: HedgeOrder[] = [];
  orderSummary: any = null;
  loading = false;

  filters = {
    status: ''
  };

  // Quote modal
  showQuote = false;
  selectedOrder: HedgeOrder | null = null;
  quoteData = {
    provider: '',
    bid_rate: null as number | null,
    ask_rate: null as number | null,
    provider_reference: ''
  };

  // Execute modal
  showExecute = false;
  executeData = {
    executed_rate: null as number | null,
    bank_reference: '',
    trade_date: '',
    value_date: '',
    counterparty_bank: ''
  };

  constructor(private atlasApi: AtlasApiService) {}

  ngOnInit() {
    this.loadOrders();
    this.loadSummary();
  }

  loadOrders() {
    this.loading = true;
    const params: any = {};
    if (this.filters.status) params.status = this.filters.status;

    this.atlasApi.getOrders(params).subscribe({
      next: (data) => {
        this.orders = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading orders:', err);
        this.loading = false;
      }
    });
  }

  loadSummary() {
    this.atlasApi.getOrdersSummary().subscribe({
      next: (data) => this.orderSummary = data,
      error: (err) => console.error('Error loading summary:', err)
    });
  }

  formatStatus(status: string): string {
    const statuses: { [key: string]: string } = {
      'draft': 'Draft',
      'pending_approval': 'Pending Approval',
      'approved': 'Approved',
      'sent_to_bank': 'Sent to Bank',
      'quoted': 'Quoted',
      'executed': 'Executed',
      'cancelled': 'Cancelled',
      'rejected': 'Rejected'
    };
    return statuses[status] || status;
  }

  approveOrder(order: HedgeOrder) {
    this.atlasApi.approveOrder(order.id).subscribe({
      next: () => {
        this.loadOrders();
        this.loadSummary();
      },
      error: (err) => console.error('Error approving order:', err)
    });
  }

  rejectOrder(order: HedgeOrder) {
    const reason = prompt('Rejection reason (optional):');
    this.atlasApi.rejectOrder(order.id, reason || undefined).subscribe({
      next: () => {
        this.loadOrders();
        this.loadSummary();
      },
      error: (err) => console.error('Error rejecting order:', err)
    });
  }

  cancelOrder(order: HedgeOrder) {
    if (confirm('Cancel this order?')) {
      this.atlasApi.cancelOrder(order.id).subscribe({
        next: () => {
          this.loadOrders();
          this.loadSummary();
        },
        error: (err) => console.error('Error cancelling order:', err)
      });
    }
  }

  showQuoteModal(order: HedgeOrder) {
    this.selectedOrder = order;
    this.quoteData = { provider: '', bid_rate: null, ask_rate: null, provider_reference: '' };
    this.showQuote = true;
  }

  submitQuote() {
    if (!this.selectedOrder || !this.quoteData.provider) return;

    this.atlasApi.addQuote(this.selectedOrder.id, {
      provider: this.quoteData.provider,
      bid_rate: this.quoteData.bid_rate || undefined,
      ask_rate: this.quoteData.ask_rate || undefined,
      provider_reference: this.quoteData.provider_reference || undefined
    }).subscribe({
      next: () => {
        this.showQuote = false;
        this.loadOrders();
      },
      error: (err) => console.error('Error adding quote:', err)
    });
  }

  showExecuteModal(order: HedgeOrder) {
    this.selectedOrder = order;
    const today = new Date().toISOString().split('T')[0];
    this.executeData = {
      executed_rate: null,
      bank_reference: '',
      trade_date: today,
      value_date: today,
      counterparty_bank: ''
    };
    this.showExecute = true;
  }

  submitExecution() {
    if (!this.selectedOrder || !this.executeData.executed_rate) return;

    const order = this.selectedOrder;
    this.atlasApi.executeOrder(order.id, {
      trade_type: order.order_type,
      side: order.side,
      currency_sold: order.side === 'buy' ? 'COP' : order.currency,
      amount_sold: order.side === 'buy' ? order.amount * this.executeData.executed_rate! : order.amount,
      currency_bought: order.side === 'buy' ? order.currency : 'COP',
      amount_bought: order.side === 'buy' ? order.amount : order.amount * this.executeData.executed_rate!,
      executed_rate: this.executeData.executed_rate!,
      counterparty_bank: this.executeData.counterparty_bank || undefined,
      bank_reference: this.executeData.bank_reference || undefined,
      trade_date: this.executeData.trade_date,
      value_date: this.executeData.value_date
    }).subscribe({
      next: () => {
        this.showExecute = false;
        this.loadOrders();
        this.loadSummary();
      },
      error: (err) => console.error('Error executing order:', err)
    });
  }

  closeQuoteModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showQuote = false;
    }
  }

  closeExecuteModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showExecute = false;
    }
  }
}
