from frappe.model.document import Document

class DMCReturn(Document):
def validate(self):
if not self.dmc:
frappe.throw("DMC reference required")

    def on_submit(self):
        ## when return validated, move items from project-return-warehouse to central and create adjustments
        dmc = frappe.get_doc("DMC", self.dmc)
        project_return_wh = f"{dmc.project} - Return"
        central_wh = frappe.get_single("Stock Settings").default_warehouse

        se = frappe.get_doc({"doctype":"Stock Entry","stock_entry_type":"Material Transfer","from_warehouse":project_return_wh,"to_warehouse":central_wh,"items":[]})
        for row in self.items:
            counted = row.qty_counted or 0
            se.append("items", {"item_code": row.item_code, "qty": counted, "s_warehouse": project_return_wh, "t_warehouse": central_wh})
            ## reconcile with what was expected: compute discrepancy
            expected = self._expected_qty_from_dmc(row.item_code)
            if expected is not None and counted != expected:
                frappe.get_doc({"doctype":"DMC Log","dmc": self.dmc, "type": "Discrepancy", "details": f"Item {row.item_code}: expected {expected}, counted {counted}"}).insert()
                ## create Stock Reconciliation / Adjustment if needed (left to implement per policy)
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
