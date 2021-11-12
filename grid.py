import math
import fiona
import utm

from pyproj import CRS, Transformer
from fiona.crs import from_epsg
from shapely.geometry import box, mapping


UTM_LENGTH_NORTH = 9328094
UTM_WIDTH = 667957

tile_width = 24000
tile_height = 24000
tile_overlap = 500

cols = math.ceil(UTM_WIDTH / tile_width) + 1
rows = math.ceil((UTM_LENGTH_NORTH * 2) / tile_width) + 2
col_offset = math.ceil(cols / 2)
row_offset = math.ceil(rows / 2) + 1

false_easting = 500000
false_northing = 10000000
lonlat = CRS.from_epsg(4326)
schema = {"geometry": "Polygon", "properties": {"code": "str"}}

assert cols == 29
assert rows == 780
assert col_offset == 15
assert row_offset == 391

for utm_zone in range(1, 61):
    for south in [False, True]:
        crs_dict = {"proj": "utm", "zone": utm_zone}
        if south:
            crs_dict["south"] = True
        crs = CRS.from_dict(crs_dict)

        _, epsg_code = crs.to_authority()
        transform = Transformer.from_crs(crs, lonlat, always_xy=True)

        hem = "N" if not south else "S"

        with fiona.open(
            f"zone-{utm_zone}-{hem}.shp",
            "w",
            crs=from_epsg(epsg_code),
            schema=schema,
            driver="ESRI Shapefile",
        ) as output:
            for col in range(1, cols + 1):
                for row in range(1, rows + 1):
                    if south and row >= row_offset:
                        continue

                    if not south and row < row_offset:
                        continue

                    x_col = false_easting + (col - col_offset) * tile_width + (tile_width / 2)
                    y_row = (row - row_offset) * tile_height + (tile_height / 2)

                    if south:
                        y_row += false_northing

                    xmin = x_col - tile_width / 2 - tile_overlap
                    ymin = y_row - tile_height / 2 - tile_overlap
                    xmax = x_col + tile_width / 2 + tile_overlap
                    ymax = y_row + tile_height / 2 + tile_overlap

                    x_min_ll, y_min_ll = transform.transform(xmin, ymin)
                    x_max_ll, y_max_ll = transform.transform(xmax, ymax)

                    bl_zone = utm.latlon_to_zone_number(y_min_ll, x_min_ll)  # bottom left
                    tr_zone = utm.latlon_to_zone_number(y_max_ll, x_max_ll)  # top right

                    if all(map(lambda z: z != utm_zone, [bl_zone, tr_zone])):
                        # tile lies completely outside of the current zone
                        continue

                    tile = box(xmin, ymin, xmax, ymax)

                    output.write(
                        {
                            "geometry": mapping(tile),
                            "properties": dict(code=f"{utm_zone}{row:03}{col:02}"),
                        }
                    )
