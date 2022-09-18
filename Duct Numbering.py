"""
Reorder an incoming list of fabparts to prep them for renumbering
"""
import math
import clr

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Structure import *

clr.AddReference('System')
from System.Collections.Generic import List

clr.AddReference('RevitNodes')
import Revit
clr.ImportExtensions(Revit.GeometryConversion)
clr.ImportExtensions(Revit.Elements)

clr.AddReference('RevitServices')
import RevitServices
from RevitServices.Persistence import DocumentManager

doc = DocumentManager.Instance.CurrentDBDocument
uidoc=DocumentManager.Instance.CurrentUIApplication.ActiveUIDocument

#Sorts a list of fabricationparts by their distance from an origin point
def sortFabPartsByDistanceFromOrigin(StartPointList, Origin):
	tempList = []
	for item in StartPointList:
		distance = Origin.DistanceTo(list(item.ConnectorManager.Connectors)[0].Origin)
		tempList.append((item, distance))
	tempList = sorted(tempList, key=lambda x: x[1])
	
	startPoints = [startpoint[0] for startpoint in tempList]
	return startPoints

#Method to get an ordered list of fabparts from a single startpoint
def GetOutput(startpoint, FabPartList):
	output = []
	branches, allTaps = FindAllBranches(startpoint, FabPartList) #Return all the branches and any tap Fabpart connected to the branches
	level, longestRoute, b = FindLongestRoute(branches) #From the branches, return the longest route in the system
	b = b[::-1] #Reverse the tap fabparts list so first ones seen are at the start of the list
	
	#Append branches to the output before taps
	output.extend(longestRoute)
	output.extend(Flatten(b))
	
	#Remove used fabparts to speed up process for future iterations
	for i in output:
		try:
			FabPartList.remove(i)
		except:
			continue
			
	#Recursive call for tap connections. These branches are appended to output after
	if allTaps != []:
		for tap in allTaps:
			if tap not in output:
				output.extend(GetOutput(tap, FabPartList))
	
	return output

#Recursive method to find all the branches in a duct route and all the tap connections
def FindAllBranches(FabPartInput, FabPartList):	

	allBranches = [] #All the branches in the route as a nested list
	allTaps = [] #All the taps attached to the main branches ordered from first to last seen
	listLength = len(FabPartList)
	
	FabPartList.remove(FabPartInput)

	allBranches.append(FabPartInput)
	
	nextFabPart, taps = FindNextFabPart(FabPartInput, FabPartList)
	allTaps.extend(taps)
	
	count = 0
	stop = 0
	#Iterates through a branch and appends the next fabpart it sees to allBranches
	while(count < (listLength + 1) and stop == 0):
		count += 1
		branch = []
		#Case if only one fabpart is connected to the input. Append allBranches.
		if len(nextFabPart) == 1:
			FabPartList.remove(nextFabPart[0])
			allBranches.append(nextFabPart[0])
			nextFabPart, taps = FindNextFabPart(nextFabPart[0], FabPartList)
			allTaps.extend(taps)
		#Case for two or more connected fabparts. Recursively call this function and append the output list to allBranches
		elif len(nextFabPart) > 1:
			currentBranch = []
			tempList = deepcopy(FabPartList)
			for fabpart in nextFabPart:
				if fabpart not in currentBranch:
					currentBranch, taps = FindAllBranches(fabpart, tempList)
					allTaps.extend(taps)
					allBranches.append(currentBranch)
			stop = 1
			
	return allBranches, allTaps
			
#Copies a list by generating a new one
def deepcopy(InputList):
	newList = [item for item in InputList]
	return newList			

#Given an input FabPart, tries to find all the fabparts that are connected to it from a list based on if the connectors are connected or nearby.
def FindNextFabPart(FabPartInput, ListOfFabparts):
	nextFabParts = []
	isInputFabPart = False
	isStraight = False
	isTap = False
	mainTaps = [] #List of taps that are connected to primary ends of a fab part
	
	#Case when input is a fabrication part
	if doc.GetElement(FabPartInput.GetTypeId()).GetType().Name == "FabricationPartType":
		inputConnectors = FabPartInput.ConnectorManager.Connectors
		inputLength = FabPartInput.CenterlineLength
		isInputFabPart = True
	#Case when input is a duct accessory or mechanical equipment
	else:
		try:
			inputConnectors = FabPartInput.MEPModel.ConnectorManager.Connectors
		#Special case for flex ducts
		except:
			inputConnectors = FabPartInput.ConnectorManager.Connectors
	
	#Check if fabpart is a straight or tap. Used later.
	if isInputFabPart:
		if FabPartInput.IsAStraight():
			isStraight = True
		elif doc.GetElement(FabPartInput.GetTypeId()).FamilyName in IN[2]:
			isTap = True
	
	#Loop through each fabpart to see if it is connected to the input
	for fabpart in ListOfFabparts:
		isConnected = 0
		isFabPart = False
		if fabpart != FabPartInput:
			connectorsToCompare = []
			#Case for fabrication parts
			if doc.GetElement(fabpart.GetTypeId()).GetType().Name == "FabricationPartType":
				connectorsToCompare = fabpart.ConnectorManager.Connectors
				isFabPart = True
			#Case for duct accessory or mechanical equipment
			else:
				try:
					connectorsToCompare = fabpart.MEPModel.ConnectorManager.Connectors
				except:
					connectorsToCompare = fabpart.ConnectorManager.Connectors
			
			#Iterate through each connector in the input and the fabpart to see if they are connected or nearby
			for connectorToCompare in connectorsToCompare:
				for inputConnector in inputConnectors:
				#
				
					#Normal Cases
					
					#Connectors are directly connected
					if connectorToCompare.IsConnectedTo(inputConnector):
						nextFabParts.append(fabpart)
						#Case when a tap is connected to the primary ends of a fabrication part. Append this fabpart to mainTaps
						if doc.GetElement(fabpart.GetTypeId()).FamilyName in IN[2] and connectorToCompare.GetMEPConnectorInfo().IsSecondary:
							mainTaps.append(fabpart)
						isConnected = 1
						break
					#Connectors are within 0.3 feet of each other
					elif not inputConnector.IsConnected and not connectorToCompare.IsConnected and inputConnector.Origin.DistanceTo(connectorToCompare.Origin) < 0.3:
						nextFabParts.append(fabpart)
						#Case when a tap is connected to the primary ends of a fabrication part. Append this fabpart to mainTaps
						if doc.GetElement(fabpart.GetTypeId()).FamilyName in IN[2] and connectorToCompare.GetMEPConnectorInfo().IsSecondary:
							mainTaps.append(fabpart)
						isConnected = 1
						break
					#
					
					#Special cases
		
					if isFabPart:
						#Input is a straight and fabpart is a body connected tap and not connected properly
						if isStraight:
							#Check fabpart is a tap, has an open connector, is within a certain distance to the straigh connectors, and then ope connector is the primary connector
							if doc.GetElement(fabpart.GetTypeId()).FamilyName in IN[2] and fabpart.ConnectorManager.UnusedConnectors.Size > 0 and inputConnector.Origin.DistanceTo(connectorToCompare.Origin) < inputLength and not connectorToCompare.IsConnected and connectorToCompare.GetMEPConnectorInfo().IsPrimary:
								primary = 1
								secondary = 2
								#Get primary connectors for the straight
								for testConnector in inputConnectors:
									if testConnector.GetMEPConnectorInfo().IsPrimary:
										primary = testConnector
									elif testConnector.GetMEPConnectorInfo().IsSecondary:
										secondary = testConnector
								straightConnectors = [primary, secondary]
								distance = primary.Origin.DistanceTo(connectorToCompare.Origin) + secondary.Origin.DistanceTo(connectorToCompare.Origin)
								try:
									#Check if tap is within a distance threshold from the straight connectors and within a distance threshold from a "bounding box" (bounding box might be the wrong term) 
									if distance < GetUnconnectedTapThreshold(FabPartInput) and 1 == TapWithinStraightBounds(connectorToCompare.Origin, straightConnectors, FabPartInput):
										nextFabParts.append(fabpart)
										isConnected = 1
										break
								except:
									pass

								
						#Reverse case to above. Input is a tap and fabpart is a straight and not connected properly
						elif isTap:
							if fabpart.IsAStraight() and FabPartInput.ConnectorManager.UnusedConnectors.Size > 0 and inputConnector.Origin.DistanceTo(connectorToCompare.Origin) < fabpart.CenterlineLength and inputConnector.GetMEPConnectorInfo().IsPrimary and not inputConnector.IsConnected:
								primary = 1
								secondary = 2
								for testConnector in connectorsToCompare:
									if testConnector.GetMEPConnectorInfo().IsPrimary:
										primary = testConnector
									elif testConnector.GetMEPConnectorInfo().IsSecondary:
										secondary = testConnector
								straightConnectors = [primary, secondary]
								distance = primary.Origin.DistanceTo(inputConnector.Origin) + secondary.Origin.DistanceTo(inputConnector.Origin)
								try:
									if distance < GetUnconnectedTapThreshold(fabpart) and 1 == TapWithinStraightBounds(inputConnector.Origin, straightConnectors, fabpart):
										nextFabParts.append(fabpart)
										isConnected = 1
										break
								except:
									pass

					
	
	#Separating taps from main branches based on family name and sorting them by distance from origin (Note: might not need to sort them)	
	tempList = []
	taps = []
	for n in nextFabParts:
		if n not in tempList and n not in taps:
			#Taps that are in the mainTaps list are appended normally
			if doc.GetElement(n.GetTypeId()).FamilyName not in IN[2] or n in mainTaps:
				tempList.append(n)
			else:
				taps.append(n)
	nextFabParts = [nextFabPart for nextFabPart in tempList]
	return nextFabParts, taps
	

#Used in FindNextFabPart to determine the threshold (distance of the tap is from each connector point on the straight) for checking if a tap is connected to the straight. 
#This function uses the length of the straight as a baseline and multiplies it by the threshold value. Then adds half the width and depth of the straight to the baseline
def GetUnconnectedTapThreshold(InputStraight):
	threshold = 1
	Length = InputStraight.CenterlineLength
	Width = InputStraight.GetParameters("Main Primary Width")[0].AsDouble()*304.5
	Depth = InputStraight.GetParameters("Main Primary Depth")[0].AsDouble()*304.5
	addedValue = (Width+Depth)/2
	
	if Length < 500:
		threshold = 1.2
	elif Length <1500:
		threshold = 1.05
	elif Length < 5000:
		threshold = 1.005
	
	thresholdLength = Length*threshold + addedValue
	return thresholdLength

#Used in FindNextFabPart for unconnected taps. Checks if the origin of the tap connection is within the bounds of the straight
def TapWithinStraightBounds(TapConnectorOrigin, straightConnectors1 , straight):
	straightConnectors = list(straightConnectors1) #Convert connector set to list
	
	#Get origin of each connector in the straight. Uses connector location as the boundary of the fabpart.
	straightConnectorOrigin1 = straightConnectors[0].Origin
	straightConnectorOrigin2 = straightConnectors[1].Origin
	
	rotation = GetRotation(straight)
	
	x = sorted([straightConnectorOrigin1.X, straightConnectorOrigin2.X])
	y = sorted([straightConnectorOrigin1.Y, straightConnectorOrigin2.Y])
	z = sorted([straightConnectorOrigin1.Z, straightConnectorOrigin2.Z])
	
	Width = straight.GetParameters("Main Primary Width")[0].AsDouble()
	Depth = straight.GetParameters("Main Primary Depth")[0].AsDouble()

	#This condition works best for straights at 0 or 90 degrees with no slope.
	if (rotation > 45 and rotation < 135) or (rotation > 215 and rotation < 315):
		x[0] = x[0]-(Width/2)-0.1
		x[1] = x[1]+(Width/2)+0.1
		z[0] = z[0]-(Depth/2)-0.1
		z[1] = z[1]+(Depth/2)+0.1
		
	else:
		y[0] = y[0]-(Width/2)-0.1
		y[1] = y[1]+(Width/2)+0.1
		z[0] = z[0]-(Depth/2)-0.1
		z[1] = z[1]+(Depth/2)+0.1
	#	
	
	xTap = TapConnectorOrigin.X
	yTap = TapConnectorOrigin.Y
	zTap = TapConnectorOrigin.Z
	
	#Check if tap origin is within bounds
	if xTap >= x[0] and xTap < x[1] and yTap >= y[0] and yTap < y[1] and zTap >= z[0] and zTap < z[1]:
		return 1
	else:
		return 0

#Recursive function that finds the longest route after running FindAllBranches and returns the length of the route, the items in the route, and the branches. This list is basically searching for the longest route down a nested list.
def FindLongestRoute(input):
   longestRoute = []
   routeToAdd = []
   branch = []
   branches = []
   level = 0
   levelToAdd = 0
   
   for i in input:
       if isinstance(i, list):
           newLevel, newRoute, branch = FindLongestRoute(i)
           branches.append(newRoute)
           branches = branch + branches

           if levelToAdd < newLevel:
               levelToAdd = newLevel
               routeToAdd = newRoute
       else:
           level += 1
           longestRoute = longestRoute + [i]

   try:
       branches.remove(routeToAdd)
   except:
       pass
   level += levelToAdd
   longestRoute = longestRoute + routeToAdd

   return level, longestRoute, branches

#Recursive function to flatten a list
def Flatten(input):
	returnList = []
	if isinstance(input, list):
		for sublist in input:
			returnList += (Flatten(sublist))
	else:
		returnList.append(input)
	
	return returnList

"""
Main Code
"""

#Inputs
inputs = UnwrapElement(IN[0])
x = 1
#

output = []
startPoints = [] #List of fabparts with "Start Point" item number
emptyInputs = [] #List of fabparts that have "Start Point" or an empty item number 

#Find Start Points and all empty inputs
for i in inputs:
	itemNumber = i.GetParameters("Item Number")[0].AsString()
	if itemNumber == "Start Point":
		startPoints.append(i)
		emptyInputs.append(i)
	elif itemNumber == "":
		emptyInputs.append(i)

if startPoints == [] and IN[3]:
	lowPriorityStartPoints = []
	for fabpart in emptyInputs:
		if doc.GetElement(fabpart.GetTypeId()).FamilyName == "Cap":
			startPoints.append(fabpart)
			break
		elif doc.GetElement(fabpart.GetTypeId()).GetType().Name == "FabricationPartType":
			numberOfConnections = fabpart.ConnectorManager.UnusedConnectors.Size
			if (numberOfConnections > 0):
				if len(FindNextFabPart(fabpart, emptyInputs)[0]) < 2:	
					lowPriorityStartPoints.append(fabpart)
	if startPoints == []:
		startPoints.append(lowPriorityStartPoints[0])
	



#Order the start points and inputs by their distance from an origin point
orderedStartPoints = []

orderedStartPoints =sortFabPartsByDistanceFromOrigin(startPoints, list(startPoints[0].ConnectorManager.Connectors)[0].Origin)

#Maybe don't need to order the inputs 
#orderedInputs = sortFabPartsByDistanceFromOrigin(emptyInputs, list(startPoints[0].ConnectorManager.Connectors)[0].Origin)

#Add mechanical equipment and duct accessories to the list
emptyInputs.extend(UnwrapElement(IN[1]))

#Iterate through each startpoint and return the ordered list of fabparts and equipment
for start in orderedStartPoints:
	if start in emptyInputs:
		tempOutput = GetOutput(start, emptyInputs)
		for i in tempOutput:
			if i in emptyInputs:
				emptyInputs.remove(i)
		output.extend(tempOutput)







if IN[3]:
	#Try to find a starting point for unnumbered fabparts and rerun the script on these strays
	tempStartPoints = []
	lowerPriorityStartPoints = []
	
	#Currently prioritize stray Caps as new startpoints and then any fabpart with less than two used connections
	for fabpart in emptyInputs:
		if doc.GetElement(fabpart.GetTypeId()).FamilyName == "Cap":
			tempStartPoints.append(fabpart)
		elif doc.GetElement(fabpart.GetTypeId()).GetType().Name == "FabricationPartType":
			numberOfConnections = fabpart.ConnectorManager.UnusedConnectors.Size
			if (numberOfConnections > 0):
				if len(FindNextFabPart(fabpart, emptyInputs)[0]) < 2:	
					lowerPriorityStartPoints.append(fabpart)
	
	tempStartPoints.extend(lowerPriorityStartPoints)
					
	for startpoint in tempStartPoints:
		if startpoint in emptyInputs:
			tempOutput = GetOutput(startpoint, emptyInputs)
			for i in tempOutput:
				if i in emptyInputs:
					emptyInputs.remove(i)
			output.extend(tempOutput)
	#


#Filter for fabrication parts
try:
	outList = []
	for o in output:
		if doc.GetElement(o.GetTypeId()).GetType().Name == "FabricationPartType":
			outList.append(o)
except:
	outList = ["Fail"]
	
OUT = outList
		