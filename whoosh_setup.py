from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, ID
import os

schema = Schema(
    label=TEXT(stored=True),   # The name/title
    url=ID(stored=True),       # The link
    desc=TEXT(stored=True)     # Description (optional)
)

if not os.path.exists("whoosh_index"):
    os.mkdir("whoosh_index")

ix = create_in("whoosh_index", schema)
writer = ix.writer()
writer.add_document(label="Leave", url="/leave", desc="Request time off")
writer.add_document(label="Schedule", url="/my_schedule", desc="View your work schedule")
writer.add_document(label="Profile", url="/profile/u2@gt.com", desc="Your personal profile")
writer.add_document(label="Org Chart", url="#orgchart", desc="See the company org chart")
writer.add_document(label="Directory", url="/directory", desc="Employee directory")
writer.add_document(label="Job Posting", url="https://arielair.hrpartner.io/jobs", desc="Open positions")
writer.add_document(label="Management Hub", url="/management_hub", desc="HR/admin tools")
writer.add_document(label="User Management", url="/admin/view_users", desc="Manage users and roles")
writer.add_document(label="HR Codes", url="/registration/view_hr_codes", desc="Onboarding codes")
writer.add_document(label="Add Employee", url="/registration/generate_hr_code", desc="Onboard new staff")
writer.commit()