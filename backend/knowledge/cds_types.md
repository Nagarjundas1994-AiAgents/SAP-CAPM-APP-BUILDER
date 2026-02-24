# SAP CDS Types Reference

All valid CDS built-in types for use in entity definitions.

## Primitive Types

| Type                        | Description                    | Usage                              |
| --------------------------- | ------------------------------ | ---------------------------------- |
| `UUID`                      | Universal unique identifier    | Primary keys: `key ID : UUID;`     |
| `String(length)`            | Variable-length string         | `name : String(100);`              |
| `LargeString`               | Unlimited string (CLOB)        | `description : LargeString;`       |
| `Integer`                   | 32-bit signed integer          | `quantity : Integer default 0;`    |
| `Int16`                     | 16-bit signed integer          | Small counters                     |
| `Int32`                     | Same as Integer                | Explicit 32-bit                    |
| `Int64`                     | 64-bit signed integer          | Large counters: `bigId : Int64;`   |
| `Decimal(precision, scale)` | Fixed-point decimal            | `price : Decimal(10,2);`           |
| `Double`                    | 64-bit floating point          | Scientific calculations            |
| `Boolean`                   | true/false                     | `isActive : Boolean default true;` |
| `Date`                      | Date without time (YYYY-MM-DD) | `birthDate : Date;`                |
| `DateTime`                  | Date + time (second precision) | `createdAt : DateTime;`            |
| `Time`                      | Time of day (HH:MM:SS)         | `startTime : Time;`                |
| `Timestamp`                 | High-precision datetime        | `eventTimestamp : Timestamp;`      |
| `LargeBinary`               | Binary data (BLOB)             | `attachment : LargeBinary;`        |

## SAP Common Aspects

```cds
using { cuid, managed, temporal } from '@sap/cds/common';

// cuid: adds key ID : UUID;
// managed: adds createdAt, createdBy, modifiedAt, modifiedBy
// temporal: adds validFrom, validTo for bitemporal data

entity Foo : cuid, managed { ... }
```

## Common Reusable Types

```cds
using { Country, Currency, Language } from '@sap/cds/common';

entity Product {
  country  : Country;     // Association to sap.common.Countries
  currency : Currency;    // Association to sap.common.Currencies
  language : Language;    // Association to sap.common.Languages
}
```

## Enum Types

```cds
type StatusCode : String enum {
    New       = 'N';
    InProcess = 'I';
    Completed = 'C';
    Cancelled = 'X';
}

type Priority : Integer enum {
    High   = 1;
    Medium = 2;
    Low    = 3;
}
```

## Array / Structured Types

```cds
type Address {
    street  : String(100);
    city    : String(50);
    country : String(3);
    zip     : String(10);
}

entity Employee {
    homeAddress : Address;
    tags        : array of String;   // HANA only
}
```

## Default Values

```cds
// String defaults use single quotes inside
status   : String(20) default 'Active';
currency : String(3) default 'USD';

// Numeric defaults
quantity : Integer default 0;
price    : Decimal(10,2) default 0.00;

// Boolean defaults
isActive : Boolean default true;

// Date/time — no literal default, use handler
// createdAt : DateTime; // set in before handler
```
