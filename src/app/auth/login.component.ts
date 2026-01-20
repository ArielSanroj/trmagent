/**
 * Login Component
 */
import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiService } from '../services/api.service';
import { NotificationService } from '../services/notification.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-container">
      <div class="login-card">
        <div class="login-header">
          <h1>TRM Agent</h1>
          <p>Agente Inteligente de Trading USD/COP</p>
        </div>

        <div class="tabs">
          <button [class.active]="!isRegister" (click)="isRegister = false">Iniciar Sesion</button>
          <button [class.active]="isRegister" (click)="isRegister = true">Registrarse</button>
        </div>

        <form (ngSubmit)="onSubmit()" class="login-form">
          <div *ngIf="isRegister" class="form-group">
            <label>Nombre Completo</label>
            <input type="text" [(ngModel)]="fullName" name="fullName"
                   placeholder="Tu nombre" required />
          </div>

          <div class="form-group">
            <label>Email</label>
            <input type="email" [(ngModel)]="email" name="email"
                   placeholder="tu@email.com" required />
          </div>

          <div class="form-group">
            <label>Contrasena</label>
            <input type="password" [(ngModel)]="password" name="password"
                   placeholder="••••••••" required minlength="8" />
          </div>

          <button type="submit" class="submit-btn" [disabled]="loading">
            {{ loading ? 'Procesando...' : (isRegister ? 'Crear Cuenta' : 'Ingresar') }}
          </button>
        </form>

        <div *ngIf="error" class="error-message">
          {{ error }}
        </div>

        <div class="demo-info">
          <p>Demo: usa cualquier email y contrasena (min 8 chars)</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .login-container {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
      padding: 20px;
    }

    .login-card {
      background: white;
      border-radius: 16px;
      padding: 40px;
      width: 100%;
      max-width: 400px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    }

    .login-header {
      text-align: center;
      margin-bottom: 30px;
    }

    .login-header h1 {
      margin: 0;
      color: #1a1a2e;
      font-size: 2rem;
    }

    .login-header p {
      color: #666;
      margin: 10px 0 0 0;
    }

    .tabs {
      display: flex;
      margin-bottom: 30px;
      border-bottom: 2px solid #eee;
    }

    .tabs button {
      flex: 1;
      padding: 12px;
      border: none;
      background: none;
      cursor: pointer;
      font-size: 1rem;
      color: #666;
      transition: all 0.3s;
    }

    .tabs button.active {
      color: #0066cc;
      border-bottom: 2px solid #0066cc;
      margin-bottom: -2px;
    }

    .form-group {
      margin-bottom: 20px;
    }

    .form-group label {
      display: block;
      margin-bottom: 8px;
      color: #333;
      font-weight: 500;
    }

    .form-group input {
      width: 100%;
      padding: 12px 16px;
      border: 2px solid #e0e0e0;
      border-radius: 8px;
      font-size: 1rem;
      transition: border-color 0.3s;
      box-sizing: border-box;
    }

    .form-group input:focus {
      outline: none;
      border-color: #0066cc;
    }

    .submit-btn {
      width: 100%;
      padding: 14px;
      background: linear-gradient(135deg, #0066cc, #0044aa);
      color: white;
      border: none;
      border-radius: 8px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: transform 0.2s, box-shadow 0.2s;
    }

    .submit-btn:hover:not(:disabled) {
      transform: translateY(-2px);
      box-shadow: 0 4px 12px rgba(0, 102, 204, 0.4);
    }

    .submit-btn:disabled {
      opacity: 0.7;
      cursor: not-allowed;
    }

    .error-message {
      margin-top: 20px;
      padding: 12px;
      background: #fee;
      color: #c00;
      border-radius: 8px;
      text-align: center;
    }

    .demo-info {
      margin-top: 20px;
      padding: 12px;
      background: #f0f7ff;
      border-radius: 8px;
      text-align: center;
    }

    .demo-info p {
      margin: 0;
      color: #0066cc;
      font-size: 0.9rem;
    }
  `]
})
export class LoginComponent {
  email = '';
  password = '';
  fullName = '';
  isRegister = false;
  loading = false;
  error = '';

  constructor(
    private api: ApiService,
    private router: Router,
    private notifications: NotificationService
  ) {
    // Redirigir si ya esta logueado
    if (this.api.isLoggedIn()) {
      this.router.navigate(['/dashboard']);
    }
  }

  async onSubmit(): Promise<void> {
    this.loading = true;
    this.error = '';

    try {
      if (this.isRegister) {
        await this.api.register(this.email, this.password, this.fullName).toPromise();
        this.notifications.success('Cuenta creada', 'Tu cuenta ha sido creada exitosamente');
        this.isRegister = false;
      } else {
        await this.api.login(this.email, this.password).toPromise();
        this.notifications.success('Bienvenido', 'Has iniciado sesion correctamente');
        this.router.navigate(['/dashboard']);
      }
    } catch (e: any) {
      this.error = e.message || 'Error de autenticacion';
    } finally {
      this.loading = false;
    }
  }
}
