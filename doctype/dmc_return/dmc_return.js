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
