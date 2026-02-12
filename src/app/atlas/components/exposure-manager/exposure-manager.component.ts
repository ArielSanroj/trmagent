/**
 * ATLAS Exposure Manager Component
 * Manage FX exposures: list, create, upload CSV
 */
import { Component, OnInit } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import {
  AtlasApiService,
  Exposure,
  ExposureSummary,
  Counterparty,
  ExposureUploadResult
} from '../../services/atlas-api.service';

@Component({
  selector: 'app-exposure-manager',
  template: `
    <div class="exposure-manager">
      <header class="page-header">
        <h1>Exposure Manager</h1>
        <div class="header-actions">
          <button class="btn btn-secondary" (click)="showUploadModal = true">
            Upload CSV
          </button>
          <button class="btn btn-primary" (click)="showCreateModal = true">
            + New Exposure
          </button>
        </div>
      </header>

      <!-- Summary Cards -->
      <section class="summary-cards" *ngIf="summary">
        <div class="summary-card">
          <h4>Total Payables</h4>
          <span class="amount">USD {{ summary.total_payables | number:'1.0-0' }}</span>
          <span class="coverage">{{ getCoveragePercent(summary.total_hedged_payables, summary.total_payables) | number:'1.1-1' }}% covered</span>
        </div>
        <div class="summary-card">
          <h4>Total Receivables</h4>
          <span class="amount">USD {{ summary.total_receivables | number:'1.0-0' }}</span>
          <span class="coverage">{{ getCoveragePercent(summary.total_hedged_receivables, summary.total_receivables) | number:'1.1-1' }}% covered</span>
        </div>
        <div class="summary-card">
          <h4>Net Exposure</h4>
          <span class="amount" [class.positive]="summary.net_exposure > 0" [class.negative]="summary.net_exposure < 0">
            USD {{ summary.net_exposure | number:'1.0-0' }}
          </span>
        </div>
        <div class="summary-card">
          <h4>Total Exposures</h4>
          <span class="amount">{{ summary.exposures_count }}</span>
        </div>
      </section>

      <!-- Filters -->
      <section class="filters">
        <select [(ngModel)]="filters.exposure_type" (change)="loadExposures()">
          <option value="">All Types</option>
          <option value="payable">Payables</option>
          <option value="receivable">Receivables</option>
        </select>
        <select [(ngModel)]="filters.status" (change)="loadExposures()">
          <option value="">All Statuses</option>
          <option value="open">Open</option>
          <option value="partially_hedged">Partially Hedged</option>
          <option value="fully_hedged">Fully Hedged</option>
        </select>
        <input type="date" [(ngModel)]="filters.due_date_from" (change)="loadExposures()" placeholder="Due from">
        <input type="date" [(ngModel)]="filters.due_date_to" (change)="loadExposures()" placeholder="Due to">
      </section>

      <!-- Exposures Table -->
      <section class="exposures-table">
        <table>
          <thead>
            <tr>
              <th>Reference</th>
              <th>Type</th>
              <th>Amount</th>
              <th>Due Date</th>
              <th>Coverage</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr *ngFor="let exp of exposures" [class]="'status-' + exp.status">
              <td>
                <strong>{{ exp.reference }}</strong>
                <br><small>{{ exp.description }}</small>
              </td>
              <td>
                <span class="type-badge" [class]="exp.exposure_type">
                  {{ exp.exposure_type === 'payable' ? 'Payable' : 'Receivable' }}
                </span>
              </td>
              <td class="amount-cell">
                {{ exp.currency }} {{ exp.amount | number:'1.0-0' }}
                <br><small class="open-amount">Open: {{ exp.amount - exp.amount_hedged | number:'1.0-0' }}</small>
              </td>
              <td>
                {{ exp.due_date | date:'mediumDate' }}
                <br><small>{{ exp.days_to_maturity }} days</small>
              </td>
              <td>
                <div class="coverage-indicator">
                  <div class="coverage-bar-mini">
                    <div class="fill" [style.width.%]="exp.hedge_percentage"></div>
                  </div>
                  <span>{{ exp.hedge_percentage | number:'1.1-1' }}%</span>
                </div>
              </td>
              <td>
                <span class="status-badge" [class]="exp.status">{{ formatStatus(exp.status) }}</span>
              </td>
              <td class="actions-cell">
                <button class="btn-icon" (click)="viewExposure(exp)" title="View">👁</button>
                <button class="btn-icon" (click)="editExposure(exp)" title="Edit">✏️</button>
                <button class="btn-icon" (click)="deleteExposure(exp)" title="Cancel">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>

        <div class="empty-state" *ngIf="exposures.length === 0 && !loading">
          <p>No exposures found. Create one or upload a CSV file.</p>
        </div>

        <div class="loading" *ngIf="loading">Loading exposures...</div>
      </section>

      <!-- Create/Edit Modal -->
      <div class="modal" *ngIf="showCreateModal" (click)="closeModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h2>{{ editingExposure ? 'Edit Exposure' : 'New Exposure' }}</h2>
          <form [formGroup]="exposureForm" (ngSubmit)="saveExposure()">
            <div class="form-row">
              <div class="form-group">
                <label>Type *</label>
                <select formControlName="exposure_type">
                  <option value="payable">Payable (Buy USD)</option>
                  <option value="receivable">Receivable (Sell USD)</option>
                </select>
              </div>
              <div class="form-group">
                <label>Reference *</label>
                <input type="text" formControlName="reference" placeholder="Invoice #, PO #">
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Amount *</label>
                <input type="number" formControlName="amount" step="0.01">
              </div>
              <div class="form-group">
                <label>Currency</label>
                <select formControlName="currency">
                  <option value="USD">USD</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Due Date *</label>
                <input type="date" formControlName="due_date">
              </div>
              <div class="form-group">
                <label>Invoice Date</label>
                <input type="date" formControlName="invoice_date">
              </div>
            </div>

            <div class="form-group">
              <label>Description</label>
              <textarea formControlName="description" rows="2"></textarea>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label>Budget Rate</label>
                <input type="number" formControlName="budget_rate" step="0.0001">
              </div>
              <div class="form-group">
                <label>Target Rate</label>
                <input type="number" formControlName="target_rate" step="0.0001">
              </div>
            </div>

            <div class="form-actions">
              <button type="button" class="btn btn-secondary" (click)="showCreateModal = false">Cancel</button>
              <button type="submit" class="btn btn-primary" [disabled]="!exposureForm.valid">
                {{ editingExposure ? 'Update' : 'Create' }}
              </button>
            </div>
          </form>
        </div>
      </div>

      <!-- Upload Modal -->
      <div class="modal" *ngIf="showUploadModal" (click)="closeModal($event)">
        <div class="modal-content" (click)="$event.stopPropagation()">
          <h2>Upload Exposures from CSV</h2>

          <div class="upload-instructions">
            <p>Upload a CSV file with the following columns:</p>
            <code>reference, type, amount, currency, due_date, counterparty, description, invoice_date</code>
            <ul>
              <li><strong>type:</strong> "payable" or "receivable"</li>
              <li><strong>due_date:</strong> YYYY-MM-DD format</li>
            </ul>
          </div>

          <div class="upload-area" [class.dragover]="isDragOver"
               (dragover)="onDragOver($event)"
               (dragleave)="onDragLeave($event)"
               (drop)="onDrop($event)">
            <input type="file" #fileInput accept=".csv" (change)="onFileSelected($event)" hidden>
            <p *ngIf="!selectedFile">
              Drag & drop a CSV file here, or
              <button class="btn-link" (click)="fileInput.click()">browse</button>
            </p>
            <p *ngIf="selectedFile">
              Selected: {{ selectedFile.name }}
              <button class="btn-link" (click)="selectedFile = null">Remove</button>
            </p>
          </div>

          <div class="upload-result" *ngIf="uploadResult">
            <h4>Upload Results</h4>
            <ul>
              <li>Total rows: {{ uploadResult.total_rows }}</li>
              <li class="success">Created: {{ uploadResult.created }}</li>
              <li class="info">Updated: {{ uploadResult.updated }}</li>
              <li class="error" *ngIf="uploadResult.errors > 0">Errors: {{ uploadResult.errors }}</li>
            </ul>
            <div class="error-details" *ngIf="uploadResult.error_details?.length > 0">
              <h5>Error Details:</h5>
              <ul>
                <li *ngFor="let err of uploadResult.error_details.slice(0, 5)">
                  Row {{ err.row }}: {{ err.error }}
                </li>
              </ul>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" class="btn btn-secondary" (click)="showUploadModal = false; uploadResult = null">
              Close
            </button>
            <button type="button" class="btn btn-primary"
                    [disabled]="!selectedFile || uploading"
                    (click)="uploadFile()">
              {{ uploading ? 'Uploading...' : 'Upload' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .exposure-manager { padding: 20px; max-width: 1400px; margin: 0 auto; }

    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    .page-header h1 { margin: 0; }
    .header-actions { display: flex; gap: 10px; }

    .btn { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
    .btn-primary { background: #007bff; color: white; }
    .btn-primary:hover { background: #0056b3; }
    .btn-primary:disabled { background: #ccc; }
    .btn-secondary { background: #6c757d; color: white; }
    .btn-secondary:hover { background: #545b62; }
    .btn-link { background: none; border: none; color: #007bff; cursor: pointer; text-decoration: underline; }

    .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
    .summary-card { background: white; border-radius: 8px; padding: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .summary-card h4 { margin: 0 0 10px; font-size: 13px; color: #666; }
    .summary-card .amount { font-size: 24px; font-weight: bold; display: block; }
    .summary-card .amount.positive { color: #28a745; }
    .summary-card .amount.negative { color: #dc3545; }
    .summary-card .coverage { font-size: 12px; color: #999; }

    .filters { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .filters select, .filters input { padding: 8px 12px; border: 1px solid #ddd; border-radius: 4px; }

    .exposures-table { background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .exposures-table table { width: 100%; border-collapse: collapse; }
    .exposures-table th, .exposures-table td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }
    .exposures-table th { background: #f8f9fa; font-weight: 600; font-size: 13px; color: #666; }
    .exposures-table small { color: #999; }

    .type-badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .type-badge.payable { background: #fff3cd; color: #856404; }
    .type-badge.receivable { background: #d4edda; color: #155724; }

    .amount-cell { text-align: right; }
    .open-amount { color: #dc3545; }

    .coverage-indicator { display: flex; align-items: center; gap: 8px; }
    .coverage-bar-mini { width: 60px; height: 6px; background: #e9ecef; border-radius: 3px; overflow: hidden; }
    .coverage-bar-mini .fill { height: 100%; background: #28a745; }

    .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; }
    .status-badge.open { background: #e9ecef; color: #495057; }
    .status-badge.partially_hedged { background: #fff3cd; color: #856404; }
    .status-badge.fully_hedged { background: #d4edda; color: #155724; }

    .actions-cell { white-space: nowrap; }
    .btn-icon { background: none; border: none; cursor: pointer; font-size: 16px; padding: 4px 8px; }
    .btn-icon:hover { background: #f0f0f0; border-radius: 4px; }

    .empty-state, .loading { padding: 40px; text-align: center; color: #666; }

    .modal { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 1000; }
    .modal-content { background: white; border-radius: 8px; padding: 30px; width: 100%; max-width: 600px; max-height: 90vh; overflow-y: auto; }
    .modal-content h2 { margin: 0 0 20px; }

    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    .form-group { margin-bottom: 15px; }
    .form-group label { display: block; margin-bottom: 5px; font-weight: 500; font-size: 13px; }
    .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; box-sizing: border-box; }
    .form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

    .upload-instructions { background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 20px; }
    .upload-instructions code { display: block; background: #e9ecef; padding: 10px; margin: 10px 0; border-radius: 4px; font-size: 12px; overflow-x: auto; }
    .upload-instructions ul { margin: 10px 0 0; padding-left: 20px; font-size: 13px; }

    .upload-area { border: 2px dashed #ddd; border-radius: 8px; padding: 40px; text-align: center; transition: border-color 0.2s; }
    .upload-area.dragover { border-color: #007bff; background: #f0f7ff; }

    .upload-result { background: #f8f9fa; padding: 15px; border-radius: 6px; margin-top: 20px; }
    .upload-result h4 { margin: 0 0 10px; }
    .upload-result ul { list-style: none; padding: 0; margin: 0; }
    .upload-result li { padding: 5px 0; }
    .upload-result li.success { color: #28a745; }
    .upload-result li.info { color: #17a2b8; }
    .upload-result li.error { color: #dc3545; }
    .error-details { margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; }
    .error-details h5 { margin: 0 0 10px; color: #dc3545; }
  `]
})
export class ExposureManagerComponent implements OnInit {
  exposures: Exposure[] = [];
  summary: ExposureSummary | null = null;
  counterparties: Counterparty[] = [];
  loading = false;

  filters = {
    exposure_type: '',
    status: '',
    due_date_from: '',
    due_date_to: ''
  };

  // Create/Edit modal
  showCreateModal = false;
  editingExposure: Exposure | null = null;
  exposureForm: FormGroup;

  // Upload modal
  showUploadModal = false;
  selectedFile: File | null = null;
  uploading = false;
  uploadResult: ExposureUploadResult | null = null;
  isDragOver = false;

  constructor(
    private atlasApi: AtlasApiService,
    private fb: FormBuilder
  ) {
    this.exposureForm = this.fb.group({
      exposure_type: ['payable', Validators.required],
      reference: ['', Validators.required],
      amount: ['', [Validators.required, Validators.min(0.01)]],
      currency: ['USD'],
      due_date: ['', Validators.required],
      invoice_date: [''],
      description: [''],
      budget_rate: [''],
      target_rate: ['']
    });
  }

  ngOnInit() {
    this.loadExposures();
    this.loadSummary();
    this.loadCounterparties();
  }

  loadExposures() {
    this.loading = true;
    const params: any = {};
    if (this.filters.exposure_type) params.exposure_type = this.filters.exposure_type;
    if (this.filters.status) params.status = this.filters.status;
    if (this.filters.due_date_from) params.due_date_from = this.filters.due_date_from;
    if (this.filters.due_date_to) params.due_date_to = this.filters.due_date_to;

    this.atlasApi.getExposures(params).subscribe({
      next: (data) => {
        this.exposures = data;
        this.loading = false;
      },
      error: (err) => {
        console.error('Error loading exposures:', err);
        this.loading = false;
      }
    });
  }

  loadSummary() {
    this.atlasApi.getExposureSummary().subscribe({
      next: (data) => this.summary = data,
      error: (err) => console.error('Error loading summary:', err)
    });
  }

  loadCounterparties() {
    this.atlasApi.getCounterparties().subscribe({
      next: (data) => this.counterparties = data,
      error: (err) => console.error('Error loading counterparties:', err)
    });
  }

  formatStatus(status: string): string {
    const statuses: { [key: string]: string } = {
      'open': 'Open',
      'partially_hedged': 'Partial',
      'fully_hedged': 'Hedged',
      'settled': 'Settled',
      'cancelled': 'Cancelled'
    };
    return statuses[status] || status;
  }

  getCoveragePercent(hedged: number, total: number): number {
    return total > 0 ? (hedged / total) * 100 : 0;
  }

  viewExposure(exp: Exposure) {
    // TODO: Implement detail view
    console.log('View exposure:', exp);
  }

  editExposure(exp: Exposure) {
    this.editingExposure = exp;
    this.exposureForm.patchValue({
      exposure_type: exp.exposure_type,
      reference: exp.reference,
      amount: exp.amount,
      currency: exp.currency,
      due_date: exp.due_date,
      invoice_date: exp.invoice_date,
      description: exp.description,
      budget_rate: exp.budget_rate,
      target_rate: exp.target_rate
    });
    this.showCreateModal = true;
  }

  deleteExposure(exp: Exposure) {
    if (confirm(`Cancel exposure ${exp.reference}?`)) {
      this.atlasApi.deleteExposure(exp.id).subscribe({
        next: () => this.loadExposures(),
        error: (err) => console.error('Error cancelling exposure:', err)
      });
    }
  }

  saveExposure() {
    if (!this.exposureForm.valid) return;

    const data = this.exposureForm.value;

    if (this.editingExposure) {
      this.atlasApi.updateExposure(this.editingExposure.id, data).subscribe({
        next: () => {
          this.showCreateModal = false;
          this.editingExposure = null;
          this.exposureForm.reset({ exposure_type: 'payable', currency: 'USD' });
          this.loadExposures();
          this.loadSummary();
        },
        error: (err) => console.error('Error updating exposure:', err)
      });
    } else {
      this.atlasApi.createExposure(data).subscribe({
        next: () => {
          this.showCreateModal = false;
          this.exposureForm.reset({ exposure_type: 'payable', currency: 'USD' });
          this.loadExposures();
          this.loadSummary();
        },
        error: (err) => console.error('Error creating exposure:', err)
      });
    }
  }

  closeModal(event: Event) {
    if (event.target === event.currentTarget) {
      this.showCreateModal = false;
      this.showUploadModal = false;
      this.editingExposure = null;
      this.uploadResult = null;
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    this.isDragOver = false;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.selectedFile = files[0];
    }
  }

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.selectedFile = input.files[0];
    }
  }

  uploadFile() {
    if (!this.selectedFile) return;

    this.uploading = true;
    this.atlasApi.uploadExposures(this.selectedFile).subscribe({
      next: (result) => {
        this.uploadResult = result;
        this.uploading = false;
        this.selectedFile = null;
        this.loadExposures();
        this.loadSummary();
      },
      error: (err) => {
        console.error('Error uploading file:', err);
        this.uploading = false;
      }
    });
  }
}
