import os
import sys

# Ensure fraud-agent is on python path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.data_store import DataStore
from tools.transactions import get_transaction, get_transaction_sequence
from tools.customers import get_customer_history
from tools.regions import get_customer_regions
from tools.cards import get_card_history
from tools.devices import get_device_connections
from tools.graph import find_shared_origins
from tools.closed_cases import get_similar_closed_cases
from tools.evidence_requests import request_customer_validation, request_step_up

ds = DataStore.get_instance()

print("--- 1. get_transaction('3514030') ---")
print(get_transaction.invoke({"transaction_id": "3514030"}))

print("\n--- 2. get_transaction_sequence('C12382', '3514030') ---")
print(get_transaction_sequence.invoke({"customer_id": "C12382", "transaction_id": "3514030"}))

print("\n--- 3. get_customer_history('C12382') ---")
print(get_customer_history.invoke({"customer_id": "C12382"}))

print("\n--- 4. get_customer_regions('C12382') ---")
print(get_customer_regions.invoke({"customer_id": "C12382"}))

print("\n--- 5. get_card_history('C12382-K1') ---")
print(get_card_history.invoke({"card_id": "C12382-K1"}))

print("\n--- 6. get_device_connections(customer_id='C12382') ---")
print(get_device_connections.invoke({"customer_id": "C12382"}))

print("\n--- 7. find_shared_origins(customer_id='C12382') ---")
print(find_shared_origins.invoke({"customer_id": "C12382"}))

print("\n--- 8. find_related_fraud(customer_id='C12382') ---")
from tools.graph import find_related_fraud
print(find_related_fraud.invoke({"customer_id": "C12382"}))

print("\n--- 9. get_similar_closed_cases(customer_id='C12382') ---")
print(get_similar_closed_cases.invoke({"customer_id": "C12382"}))

print("\n--- 10. request_customer_validation('3514030', 'Did you authorize this transaction of $77.07?') ---")
print(request_customer_validation.invoke({"transaction_id": "3514030", "question": "Did you authorize this transaction of $77.07?"}))


print("\n--- 11. request_step_up('3514030', 'C12382') ---")
print(request_step_up.invoke({"transaction_id": "3514030", "customer_id": "C12382", "reason": "Unusual risk score"}))


