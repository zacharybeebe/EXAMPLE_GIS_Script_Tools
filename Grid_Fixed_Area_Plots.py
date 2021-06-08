#### PARAMETERS____________________________________________________________________________________________________________________
#Imports
import arcpy as a
import math
import random as rr
import os


def find_min(x_list, y_list):
    x = x_list[0][0]
    for i in range(1, len(x_list)):
        if x_list[i][0] < x:
            x = x_list[i][0]

    y = y_list[0][0]
    for i in range(1, len(y_list)):
        if y_list[i][0] < y:
            y = y_list[i][0]
    return '{} {}'.format(x, y)


def find_y(x_list, y_list):
    x = x_list[0][0]
    for i in range(1, len(x_list)):
        if x_list[i][0] < x:
            x = x_list[i][0]

    y = y_list[0][0]
    for i in range(1, len(y_list)):
        if y_list[i][0] < y:
            y = y_list[i][0]
    return '{} {}'.format(x, float(y) + 1)


def find_max(x_list, y_list):
    x = x_list[0][0]
    for i in range(1, len(x_list)):
        if x_list[i][0] > x:
            x = x_list[i][0]

    y = y_list[0][0]
    for i in range(1, len(y_list)):
        if y_list[i][0] > y:
            y = y_list[i][0]
    return '{} {}'.format(x, y)




#Environment Parameters
a.env.workspace = 'in_memory'
a.env.overwriteOutput = True


#Tool Feature Inputs
basefeat = a.GetParameterAsText(0)
acresperplot = float(a.GetParameterAsText(1))
plotsize = float(a.GetParameterAsText(2))
output = a.GetParameterAsText(3)

spatial = a.Describe(basefeat).spatialReference


#Random field for acres in case input feature already has an "ACRE" field
field = ''
for i in range(10):
    field += str(chr(rr.randint(97, 122)))


a.CopyFeatures_management(basefeat, 'base_temp')
a.MakeFeatureLayer_management('base_temp', 'base_temp1')
a.AddField_management('base_temp1', field, 'SHORT', 7)
a.CalculateField_management('base_temp1', field, "!SHAPE.AREA@ACRES!", "PYTHON_9.3")


#Get total Acres of basefeat
acres = 0
with a.da.SearchCursor('base_temp1', field) as cur:
    for row in cur:
        acres += row[0]


a.AddMessage('Total Acres of Stand: {}'.format(acres))

plots_total = round(acres / acresperplot, 0)

a.AddMessage('Number of Plots: {}'.format(plots_total))

square = str(math.sqrt((acres * 43560) / (plots_total)))

a.AddMessage("Grid Size: {}' x {}'".format(int(float(square)), int(float(square))))


#Getting the min and max X/Y point values to use as delimeters for the fishnet
x_list = []
y_list = []

with a.da.SearchCursor('base_temp1', "SHAPE@") as cur_xy:
    for row in cur_xy:
        for part in row[0]:
            for point in part:
                if point:
                    x_list.append([float(point.X), point])
                    y_list.append([float(point.Y), point])


min_pt = find_min(x_list, y_list)
y_pt = find_y(x_list, y_list)
max_pt = find_max(x_list, y_list)

a.AddMessage('Completed Finding Max X and Y of Stand')


#Creating fishnet and getting the X/Y of the intersects
a.CreateFishnet_management('fishnet_temp', min_pt, y_pt, square, square, number_rows=None, number_columns=None, corner_coord=max_pt, labels='NO_LABELS', template = '#', geometry_type='POLYGON')

pt_list = []

with a.da.SearchCursor('fishnet_temp', "SHAPE@") as cur_xy:
    for row in cur_xy:
        for part in row[0]:
            for point in part:
                if (point.X, point.Y) not in pt_list:
                    pt_list.append((point.X, point.Y))

a.AddMessage('Completed Creating Fishnet')

#Creating 'in_memory' feature class to hold the point values
a.CreateFeatureclass_management('in_memory', 'pt_feat', 'POINT', template=None, has_m=None, has_z=None, spatial_reference=spatial)

for pt in pt_list:
    with a.da.InsertCursor('pt_feat', ["SHAPE@X", "SHAPE@Y"]) as cur_pt:
        cur_pt.insertRow(pt)

a.AddMessage('Completed Creating Points from Fishnet Vertices')


#Clipping points to base feat and buffering the point feature class to the desired plot size
a.Clip_analysis('pt_feat', basefeat, 'pt_feat_clip')

radius = '{} Feet'.format(math.sqrt((43560 / plotsize) / math.pi))
a.Buffer_analysis('pt_feat_clip', output, radius, 'FULL', 'ROUND', 'NONE', '', 'PLANAR')

a.AddMessage('Completed Clipping and Buffering Points to Fixed Area Plots')


#Adding fields and cleaning up attribute table
a.AddField_management(output, 'PLOT', 'SHORT', 4)
a.AddField_management(output, 'TREE_COUNT', 'SHORT', 4)
a.AddField_management(output, 'PLOT_RAD', 'DOUBLE', 3, 1)
a.AddField_management(output, 'PLOT_ACRE', 'DOUBLE', 4, 1)
a.AddField_management(output, 'TREE_ACRE', 'DOUBLE', 5, 1)

with a.da.UpdateCursor(output, ["BUFF_DIST", "ORIG_FID", "PLOT", "PLOT_RAD", "PLOT_ACRE", "TREE_ACRE"]) as cur_up:
    for row in cur_up:
        row[3] = row[0]
        row[2] = row[1]
        row[4] = plotsize
	row[5] = 0
        cur_up.updateRow(row)


a.DeleteField_management(output, "BUFF_DIST")
a.DeleteField_management(output, "ORIG_FID")


a.AddMessage('Completed Adding Fields and Cleaning Up Plots Feature')



#K:\users\zbee490\ARCPY\t11.shp

