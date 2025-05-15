
from django.db import transaction
from home.models import Committee, CommitteeMembership, Person
import pandas as pd

# Load the Excel file
df = pd.read_excel('import_files/committees.xlsx')

unmatched_names = set()
created_committees = []
created_memberships = []

@transaction.atomic
def import_committees(df):
    for _, row in df.iterrows():
        committee, created = Committee.objects.get_or_create(name=row['committee_name'])
        if created:
            created_committees.append(committee.name)

        def find_person(name):
            try:
                first, last = name.strip().split(' ', 1)
                return Person.objects.get(first_name__iexact=first.strip(), last_name__iexact=last.strip())
            except Exception:
                unmatched_names.add(name.strip())
                return None

        chair_name = row.get('committee_chairperson', '').strip()
        if chair_name and chair_name.upper() != "TBD":
            person = find_person(chair_name)
            if person:
                CommitteeMembership.objects.get_or_create(
                    person=person,
                    committee=committee,
                    role=CommitteeMembership.CHAIR
                )
                created_memberships.append((f"{person.first_name} {person.last_name}", committee.name, 'Chair'))

        members = row.get('committee_member', '')
        for name in [n.strip() for n in str(members).split(',') if n.strip()]:
            person = find_person(name)
            if person:
                CommitteeMembership.objects.get_or_create(
                    person=person,
                    committee=committee,
                    role=CommitteeMembership.MEMBER
                )
                created_memberships.append((f"{person.first_name} {person.last_name}", committee.name, 'Member'))

import_committees(df)

print(f"Created committees: {created_committees}")
print(f"Created memberships (sample): {created_memberships[:10]}")
print(f"Unmatched names: {sorted(unmatched_names)}")
