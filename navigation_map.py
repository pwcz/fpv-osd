import staticmaps

# Set GPS coordinates and download OSM data
latitude = 50.041159
longitude = 20.809571


tile_provider_OpenTopoMap = staticmaps.TileProvider(
    "opentopomap",
    url_pattern="https://$s.tile.opentopomap.org/$z/$x/$y.png",
    shards=["a", "b", "c"],
    max_zoom=17,
)

context = staticmaps.Context()
context.set_tile_provider(tile_provider_OpenTopoMap)

p1 = staticmaps.create_latlng(latitude, longitude)

context.set_center(p1)

context.set_zoom(17)
image = context.render_pillow(800, 800)
image.save("images/pillow.png")



