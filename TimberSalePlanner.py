#### PARAMETERS____________________________________________________________________________________________________________________
#Imports
import arcpy as a
import math



def convert_to_100_year_site_index(site_index_50_year):
    if site_index_50_year <= 70:
        return 100

    elif 70 < site_index_50_year <= 80:
        return math.ceil(((site_index_50_year - 70) * 1.3) + 100)

    elif 80 < site_index_50_year <= 100:
        return math.ceil(((site_index_50_year - 80) * 1.4) + 113)

    else:
        check_greater_than_200 = math.ceil(((site_index_50_year - 100) * 1.5) + 141)
        if check_greater_than_200 > 200:
            return 200
        else:
            return check_greater_than_200



#Environment Parameters
a.env.workspace = 'in_memory'
a.env.overwriteOutput = True


#Tool Feature Inputs
basefeat = a.GetParameterAsText(0)
bfgross = a.GetParameterAsText(1)
outputfeat = a.GetParameterAsText(2)
boolvdt = a.GetParameterAsText(3)
thinpct = float(a.GetParameterAsText(4)) / 100

soilfeat = a.mapping.Layer(r"\\dnr\agency\app_data_gis\qdl\core\Soils & Slope Stability\Soils - Site Index - Westside Douglas Fir.lyr")
strmfeat = a.mapping.Layer(r"\\dnr\agency\app_data_gis\qdl\core\LiDAR Derivatives\RS-Hydro Streams (Modeled State Land Water Types).lyr")
dnrlands = a.mapping.Layer(r"\\dnr\agency\app_data_gis\qdl\core\Land Cover & Land Use\DNR Land Use (Flat).lyr")
a.AddMessage("Completed Initial Data Load...")





#### INITIAL CLIPPING AND COPYING FO INPUT FEATURES_______________________________________________________________________________
#Clip Features from Base Feat to DNR Lands
a.Clip_analysis(basefeat, dnrlands, 'base_temp2')


#Buffering Base Temp 2 to include streams close-to but outside area
a.Buffer_analysis('base_temp2', 'base_temp1', "200 Feet", 'OUTSIDE_ONLY', 'ROUND', 'ALL', '', 'PLANAR')

#Union of Base temp 2 and Base temp 1
a.Union_analysis(['base_temp2', 'base_temp1'], 'base_temp')


#Clipping RS Streams from Base Feature
a.Clip_analysis(strmfeat, 'base_temp', 'strm_temp_clip')


#Clipping Soils from Base Feature
a.Clip_analysis(soilfeat, 'base_temp2', 'soil_temp_clip1')


#Clipping RSFRIS from Base Feature
a.Clip_analysis(bfgross, 'base_temp2', 'bf_temp_clip1')

a.AddMessage("Completed Initial Clipping...")





#### CALCULATING 100-YEAR SITE INDEX FROM SOILS LAYER_____________________________________________________________________________
#Dissolving all fields that have the same 50-year Site Index
a.Dissolve_management('soil_temp_clip1', 'soil_temp_clip', "MAJ_SPEC_SITE_INDEX")

#Adding and Calculating Acres Field to Temp Soil
a.AddField_management('soil_temp_clip', 'ACRES', 'SHORT', 7)
a.CalculateField_management('soil_temp_clip', 'ACRES', "!SHAPE.AREA@ACRES!", "PYTHON_9.3")

soils_data = {}

#Summing the acres field for total acres
soil_acre_lst = []
with a.da.SearchCursor('soil_temp_clip', ["ACRES", "MAJ_SPEC_SITE_INDEX"]) as cursor_soil:
    count = 0
    for row in cursor_soil:
        soils_data[count] = {'acres': float(row[0]),
                             'SI_100': convert_to_100_year_site_index(float(row[1]))}
        count += 1


total_acres = sum([soils_data[key]['acres'] for key in soils_data])

max_pct_SI_100 = 0
max_pct = 0
for key in soils_data:
    check_pct = soils_data[key]['acres'] / total_acres
    if check_pct > max_pct:
        max_pct = check_pct
        max_pct_SI_100 = soils_data[key]['SI_100']


if max_pct_SI_100 == 0:
    default_SI_100 = convert_to_100_year_site_index(108)
    a.AddMessage("Used default Site Index - buffer = {} feet".format(default_SI_100))
    SI_max_nocut = convert_to_100_year_site_index(108) - 25
else:
    a.AddMessage("Used source soils Site Index - buffer = {} feet".format(max_pct_SI_100))
    SI_max_nocut = max_pct_SI_100 - 25


a.AddMessage("Completed Soil SI 100 Year Calcs...")




#### STREAM BUFFERS__________________________________________________________________________________________________________
#Creating Temp Layers for Streams T3 and T4
a.MakeFeatureLayer_management('strm_temp_clip', 'str_3', '"MDL_WTR_TY" = 3')
a.MakeFeatureLayer_management('strm_temp_clip', 'str_4', '"MDL_WTR_TY" = 4')


#No Cut Buffers
#Buffering 25-Foot No Cut
a.Buffer_analysis('str_3', 'buf_str_25_nocut3', "25 Feet", 'FULL', 'ROUND', 'ALL', '', 'PLANAR')
a.Buffer_analysis('str_4', 'buf_str_25_nocut4', "25 Feet", 'FULL', 'ROUND', 'ALL', '', 'PLANAR')


#Union 25-Foot No Cut Buffers
a.Union_analysis(['buf_str_25_nocut3', 'buf_str_25_nocut4'], 'buf_nocut')


#Merge No Cut Buffer
a.Merge_management('buf_nocut', 'buf_nocut_merge')


#Clipping Buffer Union to Base Temp
a.Clip_analysis('buf_nocut_merge', 'base_temp2', 'buf_nocut_merge_clip')

a.AddMessage("Completed No Cut Buffering...")

#Cut (VDT) Buffers
#Buffering Off of 25-Foot No Cut
a.Buffer_analysis('buf_str_25_nocut3', 'buf_str_3', str(SI_max_nocut)+' Feet', 'OUTSIDE_ONLY', 'ROUND', 'ALL', '', 'PLANAR')
a.Buffer_analysis('buf_str_25_nocut4', 'buf_str_4', '75 Feet', 'OUTSIDE_ONLY', 'ROUND', 'ALL', '', 'PLANAR')


#Union Cut Buffers
a.Union_analysis(['buf_str_3', 'buf_str_4'], 'buf_union')


#Merge Cut Buffers
a.Merge_management('buf_union', 'buf_merge')


#Dissolve Cut Buffers
a.Dissolve_management('buf_merge', 'buf_dis')


#Clipping Buffer Union to Base Temp
a.Clip_analysis('buf_dis', 'base_temp2', 'buf_dis_clip')

a.AddMessage("Completed VDT Buffering...")



#### UNION OF BUFFERS AND BASE TEMP________________________________________________________________________________________
#Adding and Calculating helper fields for deleting VDT and No Cut
a.AddField_management('buf_nocut_merge_clip', 'help_nocut', 'SHORT', 2)
a.AddField_management('buf_dis_clip', 'help_vdt', 'SHORT', 2)

with a.da.UpdateCursor('buf_nocut_merge_clip', 'help_nocut') as cursor_no_cut:
    for row in cursor_no_cut:
        row[0] = 1
        cursor_no_cut.updateRow(row)



with a.da.UpdateCursor('buf_dis_clip', 'help_vdt') as cursor_vdt:
    for row in cursor_vdt:
        row[0] = 1
        cursor_vdt.updateRow(row)


#Union No Cut and Cut Buffer and Base feature
a.Union_analysis(['base_temp2', 'buf_dis_clip'], 'base_buf_temp1')

a.Union_analysis(['base_buf_temp1', 'buf_nocut_merge_clip'], 'base_buf_temp')



#### REMOVING NOT CUT BUFFERS FROM FEATURE_________________________________________________________________________________
#Deleting Buffers from Base Feature

if boolvdt == "false":
    a.MakeFeatureLayer_management('base_buf_temp', 'base_delbuf2', '"help_nocut" <> '+str(1))
    a.MakeFeatureLayer_management('base_delbuf2', 'base_delbuf1', '"help_vdt" <> '+str(1))

else:
    a.MakeFeatureLayer_management('base_buf_temp', 'base_delbuf1', '"help_nocut" <> '+str(1))


a.CopyFeatures_management('base_delbuf1', 'base_delbuf')

a.AddMessage("Completed VDT Creation or Removal...")

#### ADDING FIELDS TO OUTPUT_______________________________________________________________________________________________
#Adding Harvet Type Field and Calculating HARVEST field
a.AddField_management('base_delbuf', 'HARVEST', 'TEXT', "", "", 25)

if boolvdt == "true":
    with a.da.UpdateCursor('base_delbuf', ['help_vdt', 'HARVEST']) as cursor_harvest:
        for row in cursor_harvest:
            if row[0] == 1:
                row[1] = "VDT"
                cursor_harvest.updateRow(row)
            else:
                row[1] = "VRH"
                cursor_harvest.updateRow(row)
else:
    with a.da.UpdateCursor('base_delbuf', 'HARVEST') as cursor_harvest:
        for row in cursor_harvest:
            row[0] = "VRH"
            cursor_harvest.updateRow(row)


a.AddMessage("Completed Updating Harvest Field...")

#Add remaining fields
a.AddField_management('base_delbuf', 'UNIT_NM', 'TEXT', "", "", 5)
a.AddField_management('base_delbuf', 'ACRES', 'SHORT', 7)
a.AddField_management('base_delbuf', 'ACRES2', 'DOUBLE', 7, 2)


#Multipart to single part transformation
a.MultipartToSinglepart_management('base_delbuf', 'base_single')

a.AddMessage("Completed Multipart to SinglePart Transformation...")


#Calculate acres for the acres fields
a.CalculateField_management('base_single', 'ACRES', "!SHAPE.AREA@ACRES!", "PYTHON_9.3")
a.CalculateField_management('base_single', 'ACRES2', "!SHAPE.AREA@ACRES!", "PYTHON_9.3")


#Keeping only polys that are greater than an acre
a.MakeFeatureLayer_management('base_single', 'base_clean1', '"ACRES2" > 1.00')
a.CopyFeatures_management('base_clean1', 'base_clean')

a.AddMessage("Completed Units Clean Up...\nStarting Board Foot Calcs...")



#### CALCULATING BOARD FOOTAGE FROM RSFRIS POLYS__________________________________________________________________________
#Clipping RSFRIS polys to each unit and calculating board footage
a.AddField_management('base_clean', 'MBF', 'LONG', 9)
a.AddField_management('base_clean', 'MBF_AC', 'DOUBLE', 4, 1)

with a.da.UpdateCursor('base_clean', ['SHAPE@', 'HARVEST', 'ACRES', 'MBF', 'MBF_AC', 'UNIT_NM']) as cursor_mbf:
    unit = 1
    for row in cursor_mbf:

        a.Clip_analysis('bf_temp_clip1', row[0], 'bf_clip')

        a.AddField_management('bf_clip', 'ACRES', 'SHORT', 7)
        a.CalculateField_management('bf_clip', 'ACRES', "!SHAPE.AREA@ACRES!", "PYTHON_9.3")

        mbf_list = []
    	with a.da.UpdateCursor('bf_clip', ['ACRES', 'BFVOL_GROSS']) as cursor_bf_ac:
    	    for j in cursor_bf_ac:
                if j[1] is None:
                    j[1] = 0
                    cursor_bf_ac.updateRow(j)
                mbf = round(j[0] * j[1] / 1000,0)
                mbf_list.append(mbf)

    	mbfsum = sum(mbf_list)

    	if row[1] == "VRH":
    	    row[3] = int(mbfsum)
    	    row[4] = round(mbfsum / row[2], 1)
    	else:
    	    row[3] = int(mbfsum) * thinpct
    	    row[4] = round(mbfsum / row[2] * thinpct, 1)

    	row[5] = "U"+str(unit)
    	unit += 1

    	cursor_mbf.updateRow(row)


a.AddMessage("Completed Board Foot Calcs")

#### FINAL OUTPUT________________________________________________________________________________________________________
#Cleaning up the attribute table fields
desired_fields = ['FID', 'Shape', 'HARVEST', 'UNIT_NM', 'ACRES', 'MBF', 'MBF_AC']
save_fields = a.ListFields('base_clean')

for field in save_fields:
    if field.name not in desired_fields:
        a.DeleteField_management('base_clean', field.name)

#Output Final Feature to Output
a.CopyFeatures_management('base_clean', outputfeat)
