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
  templateUrl: './execution-console.component.component.html',
  styleUrls: ['./execution-console.component.component.scss'],
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
