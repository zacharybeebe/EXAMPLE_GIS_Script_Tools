#### PARAMETERS____________________________________________________________________________________________________________________
#Imports
import arcpy as a
import math


#Environment Parameters
a.env.workspace = 'in_memory'
a.env.overwriteOutput = True


#Tool Feature Inputs
basefeat = a.GetParameterAsText(0)
contours = a.GetParameterAsText(1)
outputfeat = a.GetParameterAsText(2)

spatial = a.Describe(basefeat).spatialReference

#Initial Copy to Temp Data
a.CopyFeatures_management(basefeat, 'base_temp')

#Add helper field to base temp to delete original polyline(s) later
a.AddField_management('base_temp', "helper", "SHORT", 1)
a.CalculateField_management('base_temp', "helper", "1", "PYTHON_9.3")

a.AddMessage("Completed Initial Data Load")


#### Breaking the polyline(s) into segments from the polyline vertices__________________________________________________________________
geoarray = []
linearray = []

#Getting the X and Y of the beginning and end of each vertices segment

with a.da.SearchCursor('base_temp', "SHAPE@") as cur_xy:
    for row in cur_xy:
        temp = []
        for part in row[0]:
            for point in part:
                if point:
                    temp.append((float(point.X), float(point.Y)))
        linearray.append(temp)

#Aligning the list into lists of XY points
for part in linearray:
    for i in range(len(part)):
        if i != len(part) - 1:
            geoarray.append([part[i], part[i+1]])

a.AddMessage("Completed Gathering Road Segment Points")


#Creating new line features from the vertices XYs and inserting them into base temp
with a.da.InsertCursor('base_temp', "SHAPE@") as line_cursor:
    for i in geoarray:
        arr = a.Array([a.Point(i[0][0], i[0][1]), a.Point(i[1][0], i[1][1])])
        line_cursor.insertRow([a.Polyline(arr, spatial)])

a.AddMessage("Completed Creating New Road Segments")


#### Length and Road Percent Calculations of newly created segments_____________________________________________________________________

#Adding Length and Percent Fields and calculating Length in feet
a.AddField_management('base_temp', "LENGTH", "DOUBLE", 7, 1)
a.AddField_management('base_temp', "PERCENT", "SHORT", 3)

a.CalculateField_management('base_temp', "LENGTH", "!shape.Length@feet!", "PYTHON_9.3")

a.MakeFeatureLayer_management('base_temp', 'base_temp1')
a.SelectLayerByAttribute_management('base_temp1', "NEW_SELECTION", '"helper" = 1')
a.DeleteFeatures_management('base_temp1')

a.SelectLayerByAttribute_management('base_temp1', "NEW_SELECTION", '"LENGTH" IS NULL')
a.DeleteFeatures_management('base_temp1')
a.DeleteField_management('base_temp1', "helper")

a.AddMessage("Completed New Road Attribute Tables Updates")

#Calculating road percent from intersecting contours
with a.da.UpdateCursor('base_temp1', ["SHAPE@", "LENGTH", "PERCENT"]) as cursor:
    for line in cursor:
        try:
            a.SelectLayerByLocation_management(contours, "INTERSECT", line[0], '', "NEW_SELECTION")
            cont_list = []
            with a.da.SearchCursor(contours, "CONTOUR") as cont_cursor:
                for cont in cont_cursor:
                    cont_list.append(cont[0])

            cmax = max(cont_list)
            cmin = min(cont_list)
            elev = cmax - cmin
            line[2] = elev / int(line[1]) * 100

            cursor.updateRow(line)
        except:
            next

a.AddMessage("Completed New Road Segment Percents from Contours")



####Cleaning of final output shapefile___________________________________________________________________________________________

a.SelectLayerByAttribute_management(contours, "CLEAR_SELECTION")


a.CopyFeatures_management('base_temp1', outputfeat)

a.AddMessage("Completed New Road Feature Output")