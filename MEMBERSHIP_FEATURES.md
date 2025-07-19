# APS Membership System - Feature Configuration

## Current Setup: Free Community Membership

The system is currently configured for **free membership** with all community features available to all members.

### Current Configuration
- **All 3,429 members**: Active status with full access
- **New signups**: Automatically activated as active members
- **Payment features**: Hidden in UI (but preserved in code)
- **Member-only content**: Accessible to all active members

## Settings Configuration

In `aps2026_site/settings/base.py`:

```python
# Current free membership settings
APS_FREE_MEMBERSHIP = True          # Free memberships enabled
APS_AUTO_ACTIVATE_MEMBERS = True    # New members auto-activated
```

## Switching to Paid Membership (Future)

When you're ready to implement paid features:

### 1. Update Settings
```python
# Change to paid membership model
APS_FREE_MEMBERSHIP = False         # Enable payment requirements
APS_AUTO_ACTIVATE_MEMBERS = False   # Require manual/payment activation
```

### 2. Add Stripe Configuration
```python
# Add to settings
STRIPE_PUBLIC_KEY = 'pk_live_...'   # Your Stripe public key
STRIPE_SECRET_KEY = 'sk_live_...'   # Your Stripe secret key
STRIPE_WEBHOOK_SECRET = 'whsec_...' # Your webhook secret
```

### 3. Enable Payment UI
In dashboard template (`members/templates/members/dashboard.html`):
```html
<!-- Uncomment this section -->
<a href="{% url 'membership_payment' %}" class="list-group-item list-group-item-action">
    <i class="bi bi-star"></i> Premium Features
</a>
```

### 4. Configure Membership Levels
Use Django admin to set up paid membership tiers:
- Basic Member: $0 (free tier)
- Premium Member: $150/year
- Corporate Member: $500/year

## Premium Content Strategy

### Option 1: Tiered Access
- **Free Members**: Basic directory, networking
- **Premium Members**: Research papers, exclusive content
- **Corporate Members**: All features + company listings

### Option 2: Pay-Per-Content
- **Free Members**: Full community access
- **Premium Content**: Individual papers, webinars ($5-25 each)
- **Subscription**: Unlimited access ($150/year)

## Technical Implementation Ready

All the infrastructure is in place:
- ✅ Payment processing (Stripe integration ready)
- ✅ Member status management
- ✅ Access control decorators
- ✅ Member-only page types
- ✅ Admin interface for member management

## Files That Control Paid Features

### Templates to Modify:
- `members/templates/members/dashboard.html` - Payment links
- `members/templates/members/profile.html` - Payment navigation
- `members/templates/members/payment.html` - Payment page

### Backend Logic:
- `members/views.py` - Member creation and status
- `members/payment.py` - Stripe integration
- `home/models.py` - Member-only page access control

### Settings:
- `aps2026_site/settings/base.py` - Feature flags

## Current Member Statistics
- **Total Members**: 3,429
- **Active Members**: 3,429 (100%)
- **Data Sources**: WordPress (1,453), Legacy (1,389), Merged (587)

---

*This system provides maximum flexibility - start free, grow into paid features when ready!*