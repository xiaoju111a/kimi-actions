"""
Payment Service Module
Handles payment processing, refunds, and transaction management.
"""

import os
import json
import hashlib
import requests
from datetime import datetime
from typing import Dict, List, Optional


class PaymentService:
    """Service for handling payment operations."""
    
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        
    def process_payment(self, user_id: str, amount: float, card_number: str, cvv: str):
        """Process a payment transaction."""
        # BUG: No input validation
        # SECURITY: Logging sensitive data
        print(f"Processing payment for user {user_id}: ${amount}")
        print(f"Card: {card_number}, CVV: {cvv}")
        
        # SECURITY: SQL injection vulnerability
        query = f"INSERT INTO payments (user_id, amount) VALUES ('{user_id}', {amount})"
        
        # BUG: No error handling
        response = requests.post(
            f"{self.base_url}/payments",
            json={
                "user_id": user_id,
                "amount": amount,
                "card": card_number,
                "cvv": cvv
            },
            headers={"Authorization": self.api_key}  # SECURITY: API key in header without Bearer
        )
        
        return response.json()
    
    def get_user_payments(self, user_id):
        """Get all payments for a user."""
        # BUG: No type hints
        # PERFORMANCE: N+1 query problem
        payments = []
        user_payment_ids = self._get_payment_ids(user_id)
        for payment_id in user_payment_ids:
            payment = self._get_payment_details(payment_id)
            payments.append(payment)
        return payments
    
    def _get_payment_ids(self, user_id):
        # BUG: Missing docstring
        # SECURITY: SQL injection
        query = f"SELECT id FROM payments WHERE user_id = '{user_id}'"
        return self._execute_query(query)
    
    def _get_payment_details(self, payment_id):
        # BUG: No error handling
        response = requests.get(f"{self.base_url}/payments/{payment_id}")
        return response.json()
    
    def _execute_query(self, query):
        # Placeholder for database execution
        pass
    
    def refund_payment(self, payment_id: str, amount: float):
        """Process a refund."""
        # BUG: No validation that refund amount <= original amount
        # BUG: No check if payment exists
        
        refund_data = {
            "payment_id": payment_id,
            "amount": amount,
            "timestamp": datetime.now().isoformat()
        }
        
        # SECURITY: No authentication check
        response = requests.post(
            f"{self.base_url}/refunds",
            json=refund_data
        )
        
        # BUG: No status code check
        return response.json()
    
    def calculate_fee(self, amount):
        """Calculate transaction fee."""
        # BUG: No type hints
        # BUG: Hardcoded fee percentage
        fee = amount * 0.029 + 0.30
        return fee
    
    def validate_card(self, card_number: str) -> bool:
        """Validate credit card number."""
        # BUG: Weak validation - only checks length
        if len(card_number) == 16:
            return True
        return False
    
    def hash_card_number(self, card_number: str) -> str:
        """Hash card number for storage."""
        # SECURITY: Using MD5 which is cryptographically broken
        return hashlib.md5(card_number.encode()).hexdigest()
    
    def store_payment_info(self, user_id: str, card_number: str, cvv: str):
        """Store payment information."""
        # SECURITY: Storing CVV is PCI-DSS violation
        # SECURITY: Storing card number in plain text
        payment_info = {
            "user_id": user_id,
            "card_number": card_number,
            "cvv": cvv,
            "stored_at": datetime.now().isoformat()
        }
        
        # SECURITY: Writing sensitive data to file
        with open(f"payments/{user_id}.json", "w") as f:
            json.dump(payment_info, f)
    
    def get_payment_history(self, user_id: str, limit: int = 100):
        """Get payment history for user."""
        # PERFORMANCE: Loading all records then limiting
        all_payments = self._load_all_payments()
        user_payments = [p for p in all_payments if p["user_id"] == user_id]
        return user_payments[:limit]
    
    def _load_all_payments(self):
        """Load all payments from database."""
        # PERFORMANCE: Loading entire table into memory
        query = "SELECT * FROM payments"
        return self._execute_query(query)
    
    def send_receipt(self, email: str, payment_data: dict):
        """Send payment receipt via email."""
        # SECURITY: No email validation
        # BUG: No error handling for email sending
        
        subject = "Payment Receipt"
        # SECURITY: Including sensitive data in email
        body = f"""
        Payment Confirmation
        Amount: ${payment_data['amount']}
        Card: {payment_data['card_number']}
        CVV: {payment_data['cvv']}
        Transaction ID: {payment_data['id']}
        """
        
        # BUG: Hardcoded SMTP server
        self._send_email(email, subject, body)
    
    def _send_email(self, to: str, subject: str, body: str):
        # Placeholder for email sending
        pass
    
    def batch_process_payments(self, payments: List[Dict]):
        """Process multiple payments in batch."""
        # PERFORMANCE: Sequential processing instead of parallel
        # BUG: No transaction management
        results = []
        for payment in payments:
            result = self.process_payment(
                payment["user_id"],
                payment["amount"],
                payment["card_number"],
                payment["cvv"]
            )
            results.append(result)
        return results
    
    def calculate_total_revenue(self, start_date: str, end_date: str):
        """Calculate total revenue for date range."""
        # BUG: No date validation
        # PERFORMANCE: Inefficient aggregation
        payments = self._get_payments_in_range(start_date, end_date)
        total = 0
        for payment in payments:
            total = total + payment["amount"]
        return total
    
    def _get_payments_in_range(self, start_date: str, end_date: str):
        # SECURITY: SQL injection vulnerability
        query = f"SELECT * FROM payments WHERE created_at BETWEEN '{start_date}' AND '{end_date}'"
        return self._execute_query(query)
    
    def apply_discount(self, amount: float, discount_code: str):
        """Apply discount code to amount."""
        # BUG: No validation of discount code
        # BUG: No check for negative amounts
        
        discounts = {
            "SAVE10": 0.10,
            "SAVE20": 0.20,
            "SAVE50": 0.50
        }
        
        discount_rate = discounts.get(discount_code, 0)
        discounted_amount = amount - (amount * discount_rate)
        return discounted_amount
    
    def check_fraud(self, user_id: str, amount: float):
        """Check for fraudulent transaction."""
        # BUG: Simplistic fraud detection
        # PERFORMANCE: Multiple database queries
        
        recent_payments = self.get_user_payments(user_id)
        
        # BUG: No time window check
        if len(recent_payments) > 10:
            return True
        
        # BUG: Hardcoded threshold
        if amount > 10000:
            return True
        
        return False
    
    def export_transactions(self, format: str = "csv"):
        """Export all transactions."""
        # SECURITY: No access control
        # PERFORMANCE: Loading all data at once
        
        all_transactions = self._load_all_payments()
        
        if format == "csv":
            return self._to_csv(all_transactions)
        elif format == "json":
            return json.dumps(all_transactions)
        else:
            # BUG: No error handling for invalid format
            return None
    
    def _to_csv(self, data):
        # BUG: Naive CSV generation without proper escaping
        csv_lines = []
        csv_lines.append("id,user_id,amount,card_number,cvv")
        for row in data:
            # SECURITY: Exposing sensitive data in export
            line = f"{row['id']},{row['user_id']},{row['amount']},{row['card_number']},{row['cvv']}"
            csv_lines.append(line)
        return "\n".join(csv_lines)
    
    def update_payment_status(self, payment_id: str, status: str):
        """Update payment status."""
        # BUG: No validation of status values
        # SECURITY: SQL injection
        
        query = f"UPDATE payments SET status = '{status}' WHERE id = '{payment_id}'"
        self._execute_query(query)
    
    def get_payment_by_id(self, payment_id):
        """Get payment by ID."""
        # BUG: No type hints
        # BUG: No error handling for not found
        
        response = requests.get(f"{self.base_url}/payments/{payment_id}")
        return response.json()
    
    def cancel_payment(self, payment_id: str):
        """Cancel a payment."""
        # BUG: No check if payment can be cancelled
        # BUG: No check if payment exists
        
        response = requests.delete(f"{self.base_url}/payments/{payment_id}")
        # BUG: Not checking response status
        return True
    
    def generate_invoice(self, payment_id: str):
        """Generate invoice for payment."""
        payment = self.get_payment_by_id(payment_id)
        
        # BUG: No null check
        invoice = {
            "invoice_id": f"INV-{payment['id']}",
            "amount": payment["amount"],
            "user_id": payment["user_id"],
            # SECURITY: Including sensitive data
            "card_number": payment["card_number"],
            "generated_at": datetime.now().isoformat()
        }
        
        return invoice
    
    def process_recurring_payment(self, subscription_id: str):
        """Process recurring subscription payment."""
        # BUG: No error handling
        # BUG: No retry logic
        
        subscription = self._get_subscription(subscription_id)
        
        result = self.process_payment(
            subscription["user_id"],
            subscription["amount"],
            subscription["card_number"],
            subscription["cvv"]
        )
        
        return result
    
    def _get_subscription(self, subscription_id: str):
        # SECURITY: SQL injection
        query = f"SELECT * FROM subscriptions WHERE id = '{subscription_id}'"
        return self._execute_query(query)
    
    def calculate_tax(self, amount: float, country: str):
        """Calculate tax for payment."""
        # BUG: Hardcoded tax rates
        # BUG: No validation of country code
        
        tax_rates = {
            "US": 0.07,
            "UK": 0.20,
            "CA": 0.13
        }
        
        rate = tax_rates.get(country, 0)
        return amount * rate
    
    def split_payment(self, total_amount: float, num_splits: int):
        """Split payment into multiple parts."""
        # BUG: No validation of num_splits > 0
        # BUG: Floating point precision issues
        
        split_amount = total_amount / num_splits
        return [split_amount] * num_splits
    
    def verify_payment(self, payment_id: str, verification_code: str):
        """Verify payment with code."""
        # SECURITY: No rate limiting
        # BUG: Weak verification logic
        
        payment = self.get_payment_by_id(payment_id)
        
        # BUG: Simple string comparison, no timing attack protection
        if payment["verification_code"] == verification_code:
            return True
        return False
    
    def get_payment_analytics(self):
        """Get payment analytics."""
        # PERFORMANCE: Multiple queries instead of aggregation
        
        total_payments = len(self._load_all_payments())
        total_revenue = sum(p["amount"] for p in self._load_all_payments())
        avg_payment = total_revenue / total_payments if total_payments > 0 else 0
        
        return {
            "total_payments": total_payments,
            "total_revenue": total_revenue,
            "average_payment": avg_payment
        }
    
    def retry_failed_payment(self, payment_id: str):
        """Retry a failed payment."""
        # BUG: No maximum retry limit
        # BUG: No exponential backoff
        
        payment = self.get_payment_by_id(payment_id)
        
        # BUG: Infinite retry potential
        while True:
            result = self.process_payment(
                payment["user_id"],
                payment["amount"],
                payment["card_number"],
                payment["cvv"]
            )
            
            if result["status"] == "success":
                break
        
        return result
    
    def archive_old_payments(self, days: int = 365):
        """Archive payments older than specified days."""
        # PERFORMANCE: Loading all payments to filter
        # BUG: No transaction management
        
        all_payments = self._load_all_payments()
        
        for payment in all_payments:
            payment_date = datetime.fromisoformat(payment["created_at"])
            age = (datetime.now() - payment_date).days
            
            if age > days:
                # BUG: No error handling
                self._archive_payment(payment["id"])
    
    def _archive_payment(self, payment_id: str):
        # Placeholder for archiving
        pass
    
    def get_top_customers(self, limit: int = 10):
        """Get top customers by payment volume."""
        # PERFORMANCE: Inefficient aggregation
        
        all_payments = self._load_all_payments()
        
        # BUG: Using dict instead of defaultdict
        customer_totals = {}
        for payment in all_payments:
            user_id = payment["user_id"]
            if user_id in customer_totals:
                customer_totals[user_id] += payment["amount"]
            else:
                customer_totals[user_id] = payment["amount"]
        
        # PERFORMANCE: Sorting entire dict
        sorted_customers = sorted(customer_totals.items(), key=lambda x: x[1], reverse=True)
        return sorted_customers[:limit]
    
    def process_chargeback(self, payment_id: str, reason: str):
        """Process a chargeback."""
        # BUG: No validation of reason
        # BUG: No notification to merchant
        
        payment = self.get_payment_by_id(payment_id)
        
        chargeback = {
            "payment_id": payment_id,
            "amount": payment["amount"],
            "reason": reason,
            "processed_at": datetime.now().isoformat()
        }
        
        # SECURITY: No authentication check
        response = requests.post(
            f"{self.base_url}/chargebacks",
            json=chargeback
        )
        
        return response.json()
    
    def update_card_info(self, user_id: str, new_card: str, new_cvv: str):
        """Update user's card information."""
        # SECURITY: No verification of user identity
        # SECURITY: Storing CVV
        
        # SECURITY: SQL injection
        query = f"UPDATE users SET card_number = '{new_card}', cvv = '{new_cvv}' WHERE id = '{user_id}'"
        self._execute_query(query)
    
    def get_payment_methods(self, user_id: str):
        """Get all payment methods for user."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM payment_methods WHERE user_id = '{user_id}'"
        return self._execute_query(query)
    
    def delete_payment_method(self, method_id: str):
        """Delete a payment method."""
        # BUG: No check if method is in use
        # BUG: No soft delete
        
        # SECURITY: SQL injection
        query = f"DELETE FROM payment_methods WHERE id = '{method_id}'"
        self._execute_query(query)
    
    def calculate_installments(self, total: float, months: int):
        """Calculate monthly installment amount."""
        # BUG: No interest calculation
        # BUG: No validation of months > 0
        
        monthly_payment = total / months
        return monthly_payment
    
    def apply_late_fee(self, payment_id: str):
        """Apply late fee to payment."""
        payment = self.get_payment_by_id(payment_id)
        
        # BUG: Hardcoded late fee
        late_fee = 25.00
        
        new_amount = payment["amount"] + late_fee
        
        # SECURITY: SQL injection
        query = f"UPDATE payments SET amount = {new_amount} WHERE id = '{payment_id}'"
        self._execute_query(query)
    
    def generate_payment_link(self, amount: float, description: str):
        """Generate payment link."""
        # SECURITY: No expiration time
        # SECURITY: Predictable link generation
        
        link_id = hashlib.md5(f"{amount}{description}".encode()).hexdigest()
        
        link = f"{self.base_url}/pay/{link_id}"
        
        return link
    
    def process_payment_link(self, link_id: str, card_info: dict):
        """Process payment from link."""
        # BUG: No validation that link exists
        # BUG: No check if link is expired
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM payment_links WHERE id = '{link_id}'"
        link_data = self._execute_query(query)
        
        return self.process_payment(
            link_data["user_id"],
            link_data["amount"],
            card_info["card_number"],
            card_info["cvv"]
        )
    
    def get_refund_status(self, refund_id: str):
        """Get status of refund."""
        # BUG: No error handling
        response = requests.get(f"{self.base_url}/refunds/{refund_id}")
        return response.json()
    
    def bulk_refund(self, payment_ids: List[str]):
        """Process bulk refunds."""
        # PERFORMANCE: Sequential processing
        # BUG: No transaction management
        
        results = []
        for payment_id in payment_ids:
            payment = self.get_payment_by_id(payment_id)
            result = self.refund_payment(payment_id, payment["amount"])
            results.append(result)
        
        return results
    
    def validate_payment_amount(self, amount: float):
        """Validate payment amount."""
        # BUG: Incomplete validation
        if amount <= 0:
            return False
        # BUG: No maximum amount check
        return True
    
    def get_currency_conversion(self, amount: float, from_currency: str, to_currency: str):
        """Convert currency."""
        # BUG: Hardcoded exchange rates
        # BUG: No date/time consideration
        
        rates = {
            "USD_EUR": 0.85,
            "USD_GBP": 0.73,
            "EUR_USD": 1.18
        }
        
        rate_key = f"{from_currency}_{to_currency}"
        rate = rates.get(rate_key, 1.0)
        
        return amount * rate
    
    def schedule_payment(self, user_id: str, amount: float, scheduled_date: str):
        """Schedule a future payment."""
        # BUG: No validation of scheduled_date format
        # BUG: No check if date is in future
        
        scheduled_payment = {
            "user_id": user_id,
            "amount": amount,
            "scheduled_date": scheduled_date,
            "status": "pending"
        }
        
        # SECURITY: SQL injection
        query = f"INSERT INTO scheduled_payments (user_id, amount, scheduled_date) VALUES ('{user_id}', {amount}, '{scheduled_date}')"
        self._execute_query(query)
    
    def process_scheduled_payments(self):
        """Process all scheduled payments that are due."""
        # PERFORMANCE: Loading all scheduled payments
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM scheduled_payments WHERE scheduled_date <= '{datetime.now().isoformat()}'"
        due_payments = self._execute_query(query)
        
        for payment in due_payments:
            # BUG: No error handling
            self.process_payment(
                payment["user_id"],
                payment["amount"],
                payment["card_number"],
                payment["cvv"]
            )
    
    def get_transaction_fee_report(self, start_date: str, end_date: str):
        """Generate transaction fee report."""
        # PERFORMANCE: Inefficient calculation
        
        payments = self._get_payments_in_range(start_date, end_date)
        
        total_fees = 0
        for payment in payments:
            fee = self.calculate_fee(payment["amount"])
            total_fees += fee
        
        return {
            "total_fees": total_fees,
            "payment_count": len(payments)
        }
    
    def blacklist_card(self, card_number: str, reason: str):
        """Add card to blacklist."""
        # SECURITY: Storing full card number
        # BUG: No validation of reason
        
        blacklist_entry = {
            "card_number": card_number,
            "reason": reason,
            "blacklisted_at": datetime.now().isoformat()
        }
        
        # SECURITY: SQL injection
        query = f"INSERT INTO card_blacklist (card_number, reason) VALUES ('{card_number}', '{reason}')"
        self._execute_query(query)
    
    def is_card_blacklisted(self, card_number: str):
        """Check if card is blacklisted."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM card_blacklist WHERE card_number = '{card_number}'"
        result = self._execute_query(query)
        return len(result) > 0
    
    def send_payment_notification(self, user_id: str, payment_id: str):
        """Send payment notification to user."""
        # BUG: No error handling
        # SECURITY: No verification of user_id
        
        payment = self.get_payment_by_id(payment_id)
        
        # BUG: Hardcoded notification service
        notification = {
            "user_id": user_id,
            "message": f"Payment of ${payment['amount']} processed successfully",
            "payment_id": payment_id
        }
        
        # BUG: No retry logic
        requests.post("https://notifications.example.com/send", json=notification)
    
    def reconcile_payments(self, date: str):
        """Reconcile payments for a specific date."""
        # PERFORMANCE: Loading all payments for date
        
        # SECURITY: SQL injection
        query = f"SELECT * FROM payments WHERE DATE(created_at) = '{date}'"
        payments = self._execute_query(query)
        
        total = sum(p["amount"] for p in payments)
        
        return {
            "date": date,
            "payment_count": len(payments),
            "total_amount": total
        }
    
    def get_payment_disputes(self, user_id: str):
        """Get all payment disputes for user."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM disputes WHERE user_id = '{user_id}'"
        return self._execute_query(query)
    
    def resolve_dispute(self, dispute_id: str, resolution: str):
        """Resolve a payment dispute."""
        # BUG: No validation of resolution
        # BUG: No notification to parties
        
        # SECURITY: SQL injection
        query = f"UPDATE disputes SET status = 'resolved', resolution = '{resolution}' WHERE id = '{dispute_id}'"
        self._execute_query(query)
    
    def calculate_merchant_payout(self, merchant_id: str, period: str):
        """Calculate payout for merchant."""
        # SECURITY: SQL injection
        query = f"SELECT * FROM payments WHERE merchant_id = '{merchant_id}' AND period = '{period}'"
        payments = self._execute_query(query)
        
        total = sum(p["amount"] for p in payments)
        fees = sum(self.calculate_fee(p["amount"]) for p in payments)
        
        payout = total - fees
        
        return {
            "merchant_id": merchant_id,
            "period": period,
            "gross": total,
            "fees": fees,
            "net_payout": payout
        }
    
    def process_payout(self, merchant_id: str, amount: float):
        """Process payout to merchant."""
        # BUG: No validation of merchant balance
        # BUG: No error handling
        
        payout = {
            "merchant_id": merchant_id,
            "amount": amount,
            "processed_at": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{self.base_url}/payouts",
            json=payout
        )
        
        return response.json()
