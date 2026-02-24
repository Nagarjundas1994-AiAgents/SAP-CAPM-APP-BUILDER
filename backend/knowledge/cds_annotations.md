# SAP CDS Annotations Reference

Annotations used in SAP CAP for Fiori Elements UI, OData, and semantics.

## UI Annotations (Fiori Elements)

### UI.HeaderInfo — Object Page header

```cds
annotate Entity with @(
  UI.HeaderInfo: {
    TypeName:       'Order',
    TypeNamePlural: 'Orders',
    Title:          { $Type: 'UI.DataField', Value: orderNumber },
    Description:    { $Type: 'UI.DataField', Value: status },
    ImageUrl:       imageUrl,
    TypeImageUrl:   'sap-icon://sales-order'
  }
);
```

### UI.LineItem — List Report columns

```cds
annotate Entity with @(
  UI.LineItem: [
    { $Type: 'UI.DataField', Value: name, ![@UI.Importance]: #High },
    { $Type: 'UI.DataField', Value: status, Criticality: criticality },
    { $Type: 'UI.DataFieldForAnnotation', Target: '@UI.DataPoint#price', Label: 'Price' },
    { $Type: 'UI.DataFieldForAction', Action: 'ServiceName.approve', Label: 'Approve' }
  ]
);
```

### UI.SelectionFields — Filter bar

```cds
annotate Entity with @(
  UI.SelectionFields: [ status, category, createdAt ]
);
```

### UI.FieldGroup — Form sections

```cds
annotate Entity with @(
  UI.FieldGroup#General: {
    Label: 'General Information',
    Data: [
      { Value: name },
      { Value: description },
      { Value: status }
    ]
  },
  UI.FieldGroup#Admin: {
    Label: 'Administrative',
    Data: [
      { Value: createdAt, Label: 'Created On' },
      { Value: createdBy, Label: 'Created By' },
      { Value: modifiedAt, Label: 'Modified On' }
    ]
  }
);
```

### UI.Facets — Object Page sections/tabs

```cds
annotate Entity with @(
  UI.Facets: [
    {
      $Type:  'UI.ReferenceFacet',
      ID:     'GeneralFacet',
      Label:  'General',
      Target: '@UI.FieldGroup#General'
    },
    {
      $Type:  'UI.ReferenceFacet',
      ID:     'ItemsFacet',
      Label:  'Line Items',
      Target: 'items/@UI.LineItem'    // composition child
    },
    {
      $Type:  'UI.ReferenceFacet',
      ID:     'AdminFacet',
      Label:  'Admin',
      Target: '@UI.FieldGroup#Admin'
    }
  ]
);
```

### UI.DataPoint — KPI values

```cds
annotate Entity with @(
  UI.DataPoint#status: {
    Value:        status,
    Title:        'Status',
    Criticality:  criticality
  },
  UI.DataPoint#total: {
    Value:       totalAmount,
    Title:       'Total Amount',
    ValueFormat: { ScaleFactor: 1, NumberOfFractionalDigits: 2 }
  }
);
```

### UI.Chart — Micro charts

```cds
annotate Entity with @(
  UI.Chart#revenue: {
    ChartType: #Bar,
    Measures: [amount],
    Dimensions: [category]
  }
);
```

## Common Annotations

### @Common.ValueList — Dropdown value help

```cds
annotate Entity with {
  status @Common.ValueList: {
    CollectionPath: 'StatusValues',
    Parameters: [
      { $Type: 'Common.ValueListParameterInOut', LocalDataProperty: status, ValueListProperty: 'code' },
      { $Type: 'Common.ValueListParameterDisplayOnly', ValueListProperty: 'name' }
    ]
  }
};
```

### @Common.SideEffects — Reactive updates

```cds
annotate Entity with @(
  Common.SideEffects#ItemChanged: {
    SourceProperties: ['quantity', 'unitPrice'],
    TargetProperties: ['totalAmount']
  }
);
```

### @Common.Label — Field labels

```cds
annotate Entity with {
  createdAt @Common.Label: 'Created On';
  status    @Common.Label: 'Status'  @Common.Text: statusText;
};
```

## Capabilities Annotations

```cds
// Read-only entity
annotate Entity with @(
  Capabilities.InsertRestrictions.Insertable: false,
  Capabilities.UpdateRestrictions.Updatable: false,
  Capabilities.DeleteRestrictions.Deletable: false
);

// Searchable fields
annotate Entity with @(
  Capabilities.SearchRestrictions.Searchable: true
);

// Sortable/filterable
annotate Entity with {
  name @Capabilities.SortRestrictions.NonSortableProperties;
};
```

## Semantic Annotations

```cds
annotate Entity with {
  email       @Semantics.email.address;
  phone       @Semantics.telephone.type: #work;
  firstName   @Semantics.name.givenName;
  lastName    @Semantics.name.familyName;
  amount      @Measures.ISOCurrency: currency;
  weight      @Measures.Unit: weightUnit;
  imageUrl    @Semantics.imageUrl;
};
```

## Draft Annotations

```cds
// Enable draft for root entity
annotate ServiceName.Entity with @odata.draft.enabled;

// NOT on composition children — they inherit draft from parent
```

## Authorization Annotations

```cds
@requires: 'authenticated-user'
service MyService {
  @restrict: [
    { grant: 'READ', to: 'Viewer' },
    { grant: ['CREATE', 'UPDATE'], to: 'Editor' },
    { grant: '*', to: 'Admin' }
  ]
  entity Orders as projection on db.Orders;
}
```
