# SAP CAP Business Logic Reference

JavaScript handler patterns for SAP CAP service implementations.

## Module Pattern

```javascript
const cds = require("@sap/cds");
const LOG = cds.log("my-service");

module.exports = cds.service.impl(async function () {
  const { Orders, OrderItems, Products } = this.entities;

  // Register event handlers here...
});
```

## Event Handlers

### Lifecycle Events

```javascript
// Before CREATE — validation, defaults, auto-numbering
this.before('CREATE', Orders, async (req) => { ... });

// After CREATE — side effects, notifications
this.after('CREATE', Orders, async (data, req) => { ... });

// Before UPDATE — validation, status transitions
this.before('UPDATE', Orders, async (req) => { ... });

// Before DELETE — referential integrity checks
this.before('DELETE', Orders, async (req) => { ... });

// After READ — computed fields, formatting
this.after('READ', Orders, (each) => { ... });

// Multiple events
this.before(['CREATE', 'UPDATE'], Orders, async (req) => { ... });
```

### Custom Actions (Bound)

```javascript
// Defined in CDS: action approve() returns Boolean;
this.on("approve", Orders, async (req) => {
  const { ID } = req.params[0];
  const order = await SELECT.one.from(Orders).where({ ID });
  if (order.status !== "Submitted") {
    return req.error(400, "Only submitted orders can be approved");
  }
  await UPDATE(Orders).set({ status: "Approved" }).where({ ID });
  return true;
});
```

### Custom Actions (Unbound)

```javascript
// Defined in CDS: function getDashboard() returns DashboardData;
this.on("getDashboard", async (req) => {
  const totalOrders = await SELECT.one
    .from(Orders)
    .columns("count(*) as count");
  const totalRevenue = await SELECT.one
    .from(Orders)
    .columns("sum(totalAmount) as total");
  return { totalOrders: totalOrders.count, totalRevenue: totalRevenue.total };
});
```

## CDS Query Language (cds.ql)

### SELECT

```javascript
// Single record
const order = await SELECT.one.from(Orders).where({ ID: id });

// Multiple records
const items = await SELECT.from(OrderItems).where({ parent_ID: orderId });

// With columns
const names = await SELECT.from(Products).columns("ID", "name", "price");

// Aggregations
const { total } = await SELECT.one
  .from(Orders)
  .columns("sum(totalAmount) as total");
const { count } = await SELECT.one.from(Orders).columns("count(*) as count");

// Ordering and limiting
const recent = await SELECT.from(Orders).orderBy("createdAt desc").limit(10);

// Filtering
const active = await SELECT.from(Products).where({
  status: "Active",
  stock: { ">=": 1 },
});
```

### INSERT

```javascript
await INSERT.into(Orders).entries(req.data);
await INSERT.into(OrderItems).entries([
  { parent_ID: orderId, product_ID: p1, quantity: 2 },
  { parent_ID: orderId, product_ID: p2, quantity: 1 },
]);
```

### UPDATE

```javascript
await UPDATE(Orders).set({ status: "Approved" }).where({ ID: id });
await UPDATE(Products)
  .set({ stock: { "-=": quantity } })
  .where({ ID: productId });
```

### DELETE

```javascript
await DELETE.from(OrderItems).where({ parent_ID: orderId });
```

## Common Patterns

### Auto-Numbering

```javascript
this.before("CREATE", Orders, async (req) => {
  const { count } = await SELECT.one.from(Orders).columns("count(*) as count");
  const year = new Date().getFullYear();
  const month = String(new Date().getMonth() + 1).padStart(2, "0");
  req.data.orderNumber = `ORD-${year}${month}-${String(count + 1).padStart(5, "0")}`;
});
```

### Status State Machine

```javascript
const TRANSITIONS = {
  Draft: ["Submitted"],
  Submitted: ["Approved", "Rejected"],
  Approved: ["InProcess"],
  InProcess: ["Completed", "OnHold"],
  OnHold: ["InProcess", "Cancelled"],
  Completed: [],
  Rejected: ["Draft"],
  Cancelled: [],
};

this.before("UPDATE", Orders, (req) => {
  if ("status" in req.data) {
    const allowed = TRANSITIONS[req._.query?.data?.status] || [];
    if (!allowed.includes(req.data.status)) {
      req.error(
        400,
        `Cannot transition from ${req._.query?.data?.status} to ${req.data.status}`,
        "status",
      );
    }
  }
});
```

### Cascading Calculations

```javascript
this.after(["CREATE", "UPDATE", "DELETE"], OrderItems, async (data, req) => {
  const parentID = data.parent_ID || req.data.parent_ID;
  if (!parentID) return;

  const items = await SELECT.from(OrderItems).where({ parent_ID: parentID });
  const netAmount = items.reduce(
    (sum, item) =>
      sum + item.quantity * item.unitPrice * (1 - (item.discount || 0) / 100),
    0,
  );
  const taxAmount = netAmount * 0.1; // 10% tax
  const totalAmount = netAmount + taxAmount;

  await UPDATE(Orders)
    .set({ netAmount, taxAmount, totalAmount })
    .where({ ID: parentID });
});
```

### Input Validation

```javascript
this.before(["CREATE", "UPDATE"], Orders, (req) => {
  const { email, startDate, endDate, quantity } = req.data;

  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
    req.error(400, "Invalid email format", "email");

  if (startDate && endDate && new Date(endDate) <= new Date(startDate))
    req.error(400, "End date must be after start date", "endDate");

  if (quantity !== undefined && quantity < 0)
    req.error(400, "Quantity cannot be negative", "quantity");
});
```

### Delete Guard (Referential Integrity)

```javascript
this.before("DELETE", Products, async (req) => {
  const { ID } = req.data;
  const usedInOrders = await SELECT.one
    .from(OrderItems)
    .columns("count(*) as count")
    .where({ product_ID: ID });

  if (usedInOrders.count > 0) {
    req.error(400, "Cannot delete product that is referenced in orders");
  }
});
```

### External Service Calls

```javascript
this.on("syncWithERP", async (req) => {
  const erp = await cds.connect.to("API_BUSINESS_PARTNER");
  const result = await erp.run(SELECT.from("A_BusinessPartner").limit(100));
  return result;
});
```

## Error Handling

```javascript
// Field-level error
req.error(400, "Invalid value", "fieldName");

// General error
req.error(409, "Record has been modified by another user");

// Warning (non-blocking)
req.warn(200, "Stock is running low");

// Info message
req.info(200, "Order has been submitted for approval");
```
