import sys
import os
import django

# Set up django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from api.views.analytics.global_pkg.agreement import GlobalAgreementAnalysisView
from accounts.models import User
from rest_framework.test import APIRequestFactory

def run():
    print("Initializing debug test...")
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()
    if not user:
        print("No users in db.")
        return

    req = APIRequestFactory().get('/')
    req.user = user
    view = GlobalAgreementAnalysisView()
    view.permission_classes = []
    
    # We will temporarily inject a mock catch_warnings exception handler 
    # directly into the numpy ttest_rel by overriding the function locally
    # but the easiest way is to print from inside the loop
    
    try:
        print("Calling view.get()")
        res = view.get(req)
        comp = res.data.get('global_comparison', {}).get('comparison', [])
        print(f"Found {len(comp)} comparison rows")
        for row in comp:
            print(f"[{row['group']}] {row['criterion_name']}: t={row['t_statistic']}, p={row['p_value']}, common={row['common_problems']}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    run()
