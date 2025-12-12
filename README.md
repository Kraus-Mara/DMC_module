# TO DO LIST

## - Implement permissions on project-return warehouses to prevent consumption while in 'Return:Counting'.

## - Decide and implement the exact Stock Reservation mechanism supported by your ERPNext version (Stock Reservation vs Bin.reserved_qty).

## - Implement Stock Reconciliation generation for discrepancies with business rules (loss vs damage vs adjustment policies).

## - Add unit tests for the flow: create DMC -> submit -> create_shipment -> start_return_count -> submit DMC Return

## - Secure endpoints with appropriate permission checks (System Manager vs Store Keeper roles)

## 1) Doctype: DMC

dmc/doctype/dmc/dmc.json

## 2) Doctype: DMC Item (child table)

dmc/doctype/dmc_item/dmc_item.json

## 3) Doctype: DMC Return

dmc/doctype/dmc_return/dmc_return.json

## 4) Doctype: DMC Return Item (child of DMC Return)

dmc/doctype/dmc_return_item/dmc_return_item.json

## 5) Doctype: DMC Log (for discrepancies and transfers)

dmc/doctype/dmc_log/dmc_log.json

# --- Python ---

## Python server-side: dmc/doctype/dmc/dmc.py

## Python server-side: dmc/doctype/dmc_return/dmc_return.py

# --- Javascript ---

## Client-side JS: dmc/doctype/dmc_return/dmc_return.js

## Hide any field showing expected qty and only allow qty_counted to be edited
