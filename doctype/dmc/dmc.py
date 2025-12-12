from **future** import annotations
import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

class DMC(Document):
def validate(self): ## Basic sanity checks
if not self.project:
frappe.throw("Project is required")
for row in self.items:
if row.qty_requested <= 0:
frappe.throw(f"Requested qty must be > 0 for {row.item_code}")

    def on_submit(self):
        ## Submitting a DMC triggers reservation creation
        self.create_reservations()
        self.status = "Reserved"
        self.save()

    def create_reservations(self):
        ## Prefer using Stock Reservation Entry if available
        ## Fallback: create a Stock Entry of type 'Material Reservation' or adjust Bin.reserved_qty
        for row in self.items:
            self._reserve_bin(row.item_code, row.qty_requested)
            row.qty_reserved = row.qty_requested
        frappe.msgprint(f"Reservations created for DMC {self.name}")

    def _reserve_bin(self, item_code, qty):
        ## Use Stock Reservation Entry when available
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
            ## Fallback: increment Bin.reserved_qty (risky — DB-level change)
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
            ## release reservation: try to delete Stock Reservation or decrement Bin.reserved_qty
            self._release_reservation(row.item_code, qty)

        se.insert()
        se.submit()
        self.status = "Shipped"
        self.save()
        frappe.msgprint(f"Shipment created: {se.name}")

    def _release_reservation(self, item_code, qty):
        ## remove Stock Reservation records linked to this DMC
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
        ## populate items with item_code only, do not include quantities
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
        ## log the transfer
        frappe.get_doc({"doctype":"DMC Log","dmc":self.name,"type":"Transfer","details":f"Transferred to project {target_project}: {items}"}).insert()
        return se.name
