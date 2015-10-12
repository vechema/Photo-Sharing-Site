$(function () {

    $('#map_canvas').gmap({'zoom': 2, 'disableDefaultUI': true}).bind('init', function (evt, map) {
        var bounds = map.getBounds();
        var southWest = bounds.getSouthWest();
        var northEast = bounds.getNorthEast();
        var lngSpan = northEast.lng() - southWest.lng();
        var latSpan = northEast.lat() - southWest.lat();
        for (var i = 0; i < 1000; i++) {
            var lat = southWest.lat() + latSpan * Math.random();
            var lng = southWest.lng() + lngSpan * Math.random();
            $('#map_canvas').gmap('addMarker', {
                'position': new google.maps.LatLng(lat, lng)
            }).click(function () {
                $('#map_canvas').gmap('openInfoWindow', {content: 'Hello world!'}, this);
            });
        }
        $('#map_canvas').gmap('set', 'MarkerClusterer', new MarkerClusterer(map, $(this).gmap('get', 'markers')));
        // To call methods in MarkerClusterer simply call
        // $('#map_canvas').gmap('get', 'MarkerClusterer').callingSomeMethod();
    });
});