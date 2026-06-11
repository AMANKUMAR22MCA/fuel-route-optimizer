import django, os
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from route_optimizer.routing import geocode, get_route
from route_optimizer.optimizer import optimize_fuel_stops

start = geocode('Chicago, IL')
end = geocode('Houston, TX')
route = get_route(start, end)

result = optimize_fuel_stops(start, end, route)
print('Total distance:', result['total_distance_miles'], 'miles')
print('Total gallons:', result['total_gallons_used'])
print('Total cost: $' + str(result['total_fuel_cost_usd']))
print('Number of stops:', result['num_fuel_stops'])
print()
for s in result['fuel_stops']:
    print('  Mile', s['approx_route_mile'], '-', s['truckstop_name'], 
          '(' + s['city'] + ',', s['state'] + ')', '- $' + str(s['price_per_gallon']) + '/gal',
          '- filled', s['gallons_filled'], 'gal')