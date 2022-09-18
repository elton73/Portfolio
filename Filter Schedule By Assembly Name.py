import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import *

clr.AddReference('RevitAPIUI')
from Autodesk.Revit.UI import *

clr.AddReference('System')
from System.Collections.Generic import List

clr.AddReference('RevitNodes')
import Revit
clr.ImportExtensions(Revit.GeometryConversion)
clr.ImportExtensions(Revit.Elements)

clr.AddReference('RevitServices')
import RevitServices
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager

doc = DocumentManager.Instance.CurrentDBDocument
uidoc=DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument

#Preparing input from dynamo to revit

tgtschedules = UnwrapElement(IN[0]) #new schedule created
names = IN[1] if isinstance(IN[1], list) else [IN(1)]

tgtdefinitions = []
for tgtschedule in tgtschedules:
	tgtdefinitions.append(tgtschedule.Definition)

#Do some action in a Transaction
TransactionManager.Instance.EnsureInTransaction(doc)
number = 0
for tgtdefinition in tgtdefinitions:
	tgtdefinition.ClearFilters()
	ScheduleFilter1 = ScheduleFilter(tgtdefinition.GetFieldId(0), ScheduleFilterType.Equal, names[number])
	tgtdefinition.AddFilter(ScheduleFilter1)
	number = number + 1

TransactionManager.Instance.TransactionTaskDone()

OUT = tgtschedules