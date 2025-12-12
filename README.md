# Doctypes (JSON snippets) — to create via Developer > Doctype or via fixtures

# 1) Doctype: DMC

dmc/doctype/dmc/dmc.json

{
"doctype": "DocType",
"name": "DMC",
"module": "DMC",
"custom": true,
"is_submittable": true,
"fields": [
{"fieldname":"project","label":"Project","fieldtype":"Link","options":"Project","reqd":1},
{"fieldname":"start_date","label":"Start Date","fieldtype":"Date"},
{"fieldname":"end_date","label":"End Date","fieldtype":"Date"},
{"fieldname":"items","label":"Items","fieldtype":"Table","options":"DMC Item"},
{"fieldname":"status","label":"Status","fieldtype":"Select","options":"Draft\nPending Approval\nReserved\nShipped\nReturn:Counting\nClosed\nTransferred","default":"Draft"},
{"fieldname":"warehouse","label":"Project Warehouse","fieldtype":"Link","options":"Warehouse"},
{"fieldname":"reserved_warehouse","label":"Reserved Warehouse","fieldtype":"Link","options":"Warehouse"}
],
"permissions": [{"role":"System Manager","read":1,"write":1,"create":1,"submit":1}]
}

# 2) Doctype: DMC Item (child table)

dmc/doctype/dmc_item/dmc_item.json

{
"doctype": "DocType",
"name": "DMC Item",
"module": "DMC",
"istable": true,
"fields": [
{"fieldname":"item_code","label":"Item Code","fieldtype":"Link","options":"Item","reqd":1},
{"fieldname":"uom","label":"UoM","fieldtype":"Link","options":"UOM"},
{"fieldname":"qty_requested","label":"Qty Requested","fieldtype":"Float","reqd":1},
{"fieldname":"qty_reserved","label":"Qty Reserved","fieldtype":"Float"},
{"fieldname":"qty_shipped","label":"Qty Shipped","fieldtype":"Float"},
{"fieldname":"qty_counted","label":"Qty Counted (Return)","fieldtype":"Float"}
]
}

# 3) Doctype: DMC Return

# Used to collect blind counts on return

dmc/doctype/dmc_return/dmc_return.json

{
"doctype": "DocType",
"name": "DMC Return",
"module": "DMC",
"is_submittable": true,
"fields": [
{"fieldname":"dmc","label":"DMC","fieldtype":"Link","options":"DMC","reqd":1},
{"fieldname":"project","label":"Project","fieldtype":"Link","options":"Project"},
{"fieldname":"items","label":"Items","fieldtype":"Table","options":"DMC Return Item"},
{"fieldname":"status","label":"Status","fieldtype":"Select","options":"Draft\nCounting\nValidated","default":"Draft"}
]
}

# 4) Doctype: DMC Return Item (child of DMC Return)

dmc/doctype/dmc_return_item/dmc_return_item.json

{
"doctype": "DocType",
"name": "DMC Return Item",
"module": "DMC",
"istable": true,
"fields": [
{"fieldname":"item_code","label":"Item Code","fieldtype":"Link","options":"Item","reqd":1},
{"fieldname":"qty_counted","label":"Qty Counted","fieldtype":"Float","reqd":1},
{"fieldname":"note","label":"Note","fieldtype":"Small Text"}
]
}

# 5) Doctype: DMC Log (for discrepancies and transfers)

dmc/doctype/dmc_log/dmc_log.json

{
"doctype": "DocType",
"name": "DMC Log",
"module": "DMC",
"custom": true,
"fields": [
{"fieldname":"dmc","label":"DMC","fieldtype":"Link","options":"DMC"},
{"fieldname":"timestamp","label":"Timestamp","fieldtype":"Datetime","default":"Now"},
{"fieldname":"type","label":"Type","fieldtype":"Select","options":"Discrepancy\nTransfer\nManual Adjustment"},
{"fieldname":"details","label":"Details","fieldtype":"Text"}
]
}

# ---------------------------

# Python server-side: dmc/doctype/dmc/dmc.py

# ---------------------------

from **future** import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class DMC(Document):
def validate(self): # Basic sanity checks
if not self.project:
frappe.throw("Project is required")
for row in self.items:
if row.qty_requested <= 0:
frappe.throw(f"Requested qty must be > 0 for {row.item_code}")

    def on_submit(self):
        # Submitting a DMC triggers reservation creation
        self.create_reservations()
        self.status = "Reserved"
        self.save()

    def create_reservations(self):
        # Prefer using Stock Reservation Entry if available
        # Fallback: create a Stock Entry of type 'Material Reservation' or adjust Bin.reserved_qty
        for row in self.items:
            self._reserve_bin(row.item_code, row.qty_requested)
            row.qty_reserved = row.qty_requested
        frappe.msgprint(f"Reservations created for DMC {self.name}")

    def _reserve_bin(self, item_code, qty):
        # Use Stock Reservation Entry when available
        try:
            reservation = frappe.get_doc({
                "doctype": "Stock Reservation",
                "reference_doctype": "DMC",
                "reference_name": self.name,
                "item_code": item_code,
                "reserved_qty": qty,
                "warehouse": self.warehouse or frappe.get_single("Stock Settings").default_warehouse
            })
            reservation.insert(ignore_permissions=True)
        except Exception:
            # Fallback: increment Bin.reserved_qty (risky — DB-level change)
            bin_doc = frappe.get_doc("Bin", {"item_code": item_code, "warehouse": self.warehouse})
            bin_doc.reserved_qty = (bin_doc.reserved_qty or 0) + qty
            bin_doc.save()

    @frappe.whitelist()
    def create_shipment(self):
        """Called by button: generate Stock Entry (Material Issue) sending reserved qty to project warehouse"""
        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Issue",
            "purpose": "Material Issue",
            "from_warehouse": frappe.get_single("Stock Settings").default_warehouse if not self.warehouse else self.warehouse,
            "to_warehouse": self.warehouse or f"{self.project} - Warehouse",
            "items": []
        })
        for row in self.items:
            qty = row.qty_reserved or row.qty_requested
            se.append("items", {
                "item_code": row.item_code,
                "qty": qty,
                "uom": row.uom,
                "s_warehouse": se.from_warehouse,
                "t_warehouse": se.to_warehouse
            })
            row.qty_shipped = qty
            # release reservation: try to delete Stock Reservation or decrement Bin.reserved_qty
            self._release_reservation(row.item_code, qty)

        se.insert()
        se.submit()
        self.status = "Shipped"
        self.save()
        frappe.msgprint(f"Shipment created: {se.name}")

    def _release_reservation(self, item_code, qty):
        # remove Stock Reservation records linked to this DMC
        try:
            res = frappe.get_all("Stock Reservation", filters={"reference_doctype": "DMC", "reference_name": self.name, "item_code": item_code})
            for r in res:
                doc = frappe.get_doc("Stock Reservation", r.name)
                doc.delete()
        except Exception:
            try:
                bin_doc = frappe.get_doc("Bin", {"item_code": item_code, "warehouse": self.warehouse})
                bin_doc.reserved_qty = max((bin_doc.reserved_qty or 0) - qty, 0)
                bin_doc.save()
            except Exception:
                frappe.log_error(f"Failed to release reservation for {item_code} on DMC {self.name}")

    @frappe.whitelist()
    def start_return_count(self):
        """Create a DMC Return document in Draft with no visible expected quantities"""
        dmc_return = frappe.get_doc({
            "doctype": "DMC Return",
            "dmc": self.name,
            "project": self.project,
            "status": "Counting",
            "items": []
        })
        # populate items with item_code only, do not include quantities
        for row in self.items:
            dmc_return.append("items", {"item_code": row.item_code})
        dmc_return.insert()
        return dmc_return.name

    def record_transfer_chantier_to_chantier(self, target_project, items):
        """Generate Stock Entry transferring items between project warehouses without passing central warehouse
        items: list of dicts {'item_code':..., 'qty':...}
        """
        from_wh = self.warehouse or f"{self.project} - Warehouse"
        to_wh = f"{target_project} - Warehouse"
        se = frappe.get_doc({
            "doctype": "Stock Entry",
            "stock_entry_type": "Material Transfer",
            "from_warehouse": from_wh,
            "to_warehouse": to_wh,
            "items": []
        })
        for it in items:
            se.append("items", {"item_code": it['item_code'], "qty": it['qty'], "s_warehouse": from_wh, "t_warehouse": to_wh})
        se.insert()
        se.submit()
        # log the transfer
        frappe.get_doc({"doctype":"DMC Log","dmc":self.name,"type":"Transfer","details":f"Transferred to project {target_project}: {items}"}).insert()
        return se.name

# ---------------------------

# Python server-side: dmc/doctype/dmc_return/dmc_return.py

# ---------------------------

from frappe.model.document import Document

class DMCReturn(Document):
def validate(self):
if not self.dmc:
frappe.throw("DMC reference required")

    def on_submit(self):
        # when return validated, move items from project-return-warehouse to central and create adjustments
        dmc = frappe.get_doc("DMC", self.dmc)
        project_return_wh = f"{dmc.project} - Return"
        central_wh = frappe.get_single("Stock Settings").default_warehouse

        se = frappe.get_doc({"doctype":"Stock Entry","stock_entry_type":"Material Transfer","from_warehouse":project_return_wh,"to_warehouse":central_wh,"items":[]})
        for row in self.items:
            counted = row.qty_counted or 0
            se.append("items", {"item_code": row.item_code, "qty": counted, "s_warehouse": project_return_wh, "t_warehouse": central_wh})
            # reconcile with what was expected: compute discrepancy
            expected = self._expected_qty_from_dmc(row.item_code)
            if expected is not None and counted != expected:
                frappe.get_doc({"doctype":"DMC Log","dmc": self.dmc, "type": "Discrepancy", "details": f"Item {row.item_code}: expected {expected}, counted {counted}"}).insert()
                # create Stock Reconciliation / Adjustment if needed (left to implement per policy)
        se.insert()
        se.submit()

    def _expected_qty_from_dmc(self, item_code):
        try:
            dmc = frappe.get_doc("DMC", self.dmc)
            for r in dmc.items:
                if r.item_code == item_code:
                    return r.qty_shipped or r.qty_reserved or r.qty_requested
        except Exception:
            return None

# ---------------------------

# Client-side JS: dmc/doctype/dmc_return/dmc_return.js

# Hide any field showing expected qty and only allow qty_counted to be edited

frappe.ui.form.on('DMC Return', {
refresh: function(frm) {
// ensure grid does not show any expected qty columns
frm.fields_dict['items'].grid.wrapper.find('.grid-body .data-row').each(function() {
// no-op, we control columns via child doctype; ensure only qty_counted is visible
});
}
});

// Client script for DMC: hide reserved/shipped/\_requested quantities from return creation
frappe.ui.form.on('DMC', {
refresh: function(frm) {
// add buttons
if (frm.doc.docstatus==1 && frm.doc.status=='Shipped') {
frm.add_custom_button('Start Return Count', function() {
frappe.call({
method: 'dmc.dmc.doctype.dmc.dmc.DMC.start_return_count',
args: { 'dmc': frm.doc.name },
callback: function(r) {
if (r.message) {
frappe.set_route('Form','DMC Return', r.message);
}
}
});
});
frm.add_custom_button('Create Shipment', function() {
frappe.call({
method: 'dmc.dmc.doctype.dmc.dmc.DMC.create_shipment',
args: { 'dmc': frm.doc.name },
callback: function(r){ if(!r.exc) frm.reload_doc(); }
});
});
}
}
});

# ---------------------------

# Notes / To-do (in-file):

# - Implement permissions on project-return warehouses to prevent consumption while in 'Return:Counting'.

# - Decide and implement the exact Stock Reservation mechanism supported by your ERPNext version (Stock Reservation vs Bin.reserved_qty).

# - Implement Stock Reconciliation generation for discrepancies with business rules (loss vs damage vs adjustment policies).

# - Add unit tests for the flow: create DMC -> submit -> create_shipment -> start_return_count -> submit DMC Return

# - Secure endpoints with appropriate permission checks (System Manager vs Store Keeper roles)
