import styled from '@emotion/styled';
import groupBy from 'lodash/groupBy';
import moment from 'moment-timezone';

import type {SelectValue} from 'sentry/types/core';

type TimezoneGroup =
  | null
  | 'Other'
  | 'US/Canada'
  | 'America'
  | 'Europe'
  | 'Australia'
  | 'Asia'
  | 'Indian'
  | 'Africa'
  | 'Pacific'
  | 'Atlantic'
  | 'Antarctica'
  | 'Arctic';

const timezones: Array<[group: TimezoneGroup, value: string, label: string]> = [
  ['Other', 'UTC', 'UTC'],
  ['Other', 'GMT', 'GMT'],

  // Group US higher-ish since
  ['US/Canada', 'US/Eastern', 'Eastern'],
  ['US/Canada', 'US/Central', 'Central'],
  ['US/Canada', 'US/Arizona', 'Arizona'],
  ['US/Canada', 'US/Mountain', 'Mountain'],
  ['US/Canada', 'US/Pacific', 'Pacific'],
  ['US/Canada', 'US/Alaska', 'Alaska'],
  ['US/Canada', 'US/Hawaii', 'Hawaii'],
  ['US/Canada', 'Canada/Newfoundland', 'Newfoundland'],
  ['US/Canada', 'Canada/Atlantic', 'Atlantic'],
  ['US/Canada', 'Canada/Eastern', 'Canadian Eastern'],
  ['US/Canada', 'Canada/Central', 'Canadian Central'],
  ['US/Canada', 'Canada/Mountain', 'Canadian Mountain'],
  ['US/Canada', 'Canada/Pacific', 'Canadian Pacific'],

  ['America', 'America/Danmarkshavn', 'Danmarkshavn'],
  ['America', 'America/Scoresbysund', 'Scoresbysund'],
  ['America', 'America/Noronha', 'Noronha'],
  ['America', 'America/Araguaina', 'Araguaina'],
  ['America', 'America/Argentina/Buenos_Aires', 'Argentina / Buenos Aires'],
  ['America', 'America/Argentina/Catamarca', 'Argentina / Catamarca'],
  ['America', 'America/Argentina/Cordoba', 'Argentina / Cordoba'],
  ['America', 'America/Argentina/Jujuy', 'Argentina / Jujuy'],
  ['America', 'America/Argentina/La_Rioja', 'Argentina / La Rioja'],
  ['America', 'America/Argentina/Mendoza', 'Argentina / Mendoza'],
  ['America', 'America/Argentina/Rio_Gallegos', 'Argentina / Rio Gallegos'],
  ['America', 'America/Argentina/Salta', 'Argentina / Salta'],
  ['America', 'America/Argentina/San_Juan', 'Argentina / San Juan'],
  ['America', 'America/Argentina/San_Luis', 'Argentina / San Luis'],
  ['America', 'America/Argentina/Tucuman', 'Argentina / Tucuman'],
  ['America', 'America/Argentina/Ushuaia', 'Argentina / Ushuaia'],
  ['America', 'America/Asuncion', 'Asuncion'],
  ['America', 'America/Bahia', 'Bahia'],
  ['America', 'America/Belem', 'Belem'],
  ['America', 'America/Campo_Grande', 'Campo Grande'],
  ['America', 'America/Cayenne', 'Cayenne'],
  ['America', 'America/Cuiaba', 'Cuiaba'],
  ['America', 'America/Fortaleza', 'Fortaleza'],
  ['America', 'America/Godthab', 'Godthab'],
  ['America', 'America/Maceio', 'Maceio'],
  ['America', 'America/Miquelon', 'Miquelon'],
  ['America', 'America/Montevideo', 'Montevideo'],
  ['America', 'America/Paramaribo', 'Paramaribo'],
  ['America', 'America/Recife', 'Recife'],
  ['America', 'America/Santarem', 'Santarem'],
  ['America', 'America/Santiago', 'Santiago'],
  ['America', 'America/Sao_Paulo', 'Sao Paulo'],
  ['America', 'America/St_Johns', 'St Johns'],
  ['America', 'America/Anguilla', 'Anguilla'],
  ['America', 'America/Antigua', 'Antigua'],
  ['America', 'America/Aruba', 'Aruba'],
  ['America', 'America/Barbados', 'Barbados'],
  ['America', 'America/Blanc-Sablon', 'Blanc-Sablon'],
  ['America', 'America/Boa_Vista', 'Boa Vista'],
  ['America', 'America/Caracas', 'Caracas'],
  ['America', 'America/Curacao', 'Curacao'],
  ['America', 'America/Dominica', 'Dominica'],
  ['America', 'America/Glace_Bay', 'Glace Bay'],
  ['America', 'America/Goose_Bay', 'Goose Bay'],
  ['America', 'America/Grenada', 'Grenada'],
  ['America', 'America/Guadeloupe', 'Guadeloupe'],
  ['America', 'America/Guyana', 'Guyana'],
  ['America', 'America/Halifax', 'Halifax'],
  ['America', 'America/Kralendijk', 'Kralendijk'],
  ['America', 'America/La_Paz', 'La Paz'],
  ['America', 'America/Lower_Princes', 'Lower Princes'],
  ['America', 'America/Manaus', 'Manaus'],
  ['America', 'America/Marigot', 'Marigot'],
  ['America', 'America/Martinique', 'Martinique'],
  ['America', 'America/Moncton', 'Moncton'],
  ['America', 'America/Montserrat', 'Montserrat'],
  ['America', 'America/Port_of_Spain', 'Port of Spain'],
  ['America', 'America/Porto_Velho', 'Porto Velho'],
  ['America', 'America/Puerto_Rico', 'Puerto Rico'],
  ['America', 'America/Santo_Domingo', 'Santo Domingo'],
  ['America', 'America/St_Barthelemy', 'St Barthelemy'],
  ['America', 'America/St_Kitts', 'St Kitts'],
  ['America', 'America/St_Lucia', 'St Lucia'],
  ['America', 'America/St_Thomas', 'St Thomas'],
  ['America', 'America/St_Vincent', 'St Vincent'],
  ['America', 'America/Thule', 'Thule'],
  ['America', 'America/Tortola', 'Tortola'],
  ['America', 'America/Atikokan', 'Atikokan'],
  ['America', 'America/Bogota', 'Bogota'],
  ['America', 'America/Cancun', 'Cancun'],
  ['America', 'America/Cayman', 'Cayman'],
  ['America', 'America/Detroit', 'Detroit'],
  ['America', 'America/Eirunepe', 'Eirunepe'],
  ['America', 'America/Grand_Turk', 'Grand Turk'],
  ['America', 'America/Guayaquil', 'Guayaquil'],
  ['America', 'America/Havana', 'Havana'],
  ['America', 'America/Indiana/Indianapolis', 'Indiana / Indianapolis'],
  ['America', 'America/Indiana/Marengo', 'Indiana / Marengo'],
  ['America', 'America/Indiana/Petersburg', 'Indiana / Petersburg'],
  ['America', 'America/Indiana/Vevay', 'Indiana / Vevay'],
  ['America', 'America/Indiana/Vincennes', 'Indiana / Vincennes'],
  ['America', 'America/Indiana/Winamac', 'Indiana / Winamac'],
  ['America', 'America/Iqaluit', 'Iqaluit'],
  ['America', 'America/Jamaica', 'Jamaica'],
  ['America', 'America/Kentucky/Louisville', 'Kentucky / Louisville'],
  ['America', 'America/Kentucky/Monticello', 'Kentucky / Monticello'],
  ['America', 'America/Lima', 'Lima'],
  ['America', 'America/Nassau', 'Nassau'],
  ['America', 'America/New_York', 'New York'],
  ['America', 'America/Nipigon', 'Nipigon'],
  ['America', 'America/Panama', 'Panama'],
  ['America', 'America/Pangnirtung', 'Pangnirtung'],
  ['America', 'America/Port-au-Prince', 'Port-au-Prince'],
  ['America', 'America/Rio_Branco', 'Rio Branco'],
  ['America', 'America/Thunder_Bay', 'Thunder Bay'],
  ['America', 'America/Toronto', 'Toronto'],
  ['America', 'America/Bahia_Banderas', 'Bahia Banderas'],
  ['America', 'America/Belize', 'Belize'],
  ['America', 'America/Chicago', 'Chicago'],
  ['America', 'America/Costa_Rica', 'Costa Rica'],
  ['America', 'America/El_Salvador', 'El Salvador'],
  ['America', 'America/Guatemala', 'Guatemala'],
  ['America', 'America/Indiana/Knox', 'Indiana / Knox'],
  ['America', 'America/Indiana/Tell_City', 'Indiana / Tell City'],
  ['America', 'America/Managua', 'Managua'],
  ['America', 'America/Matamoros', 'Matamoros'],
  ['America', 'America/Menominee', 'Menominee'],
  ['America', 'America/Merida', 'Merida'],
  ['America', 'America/Mexico_City', 'Mexico City'],
  ['America', 'America/Monterrey', 'Monterrey'],
  ['America', 'America/North_Dakota/Beulah', 'North Dakota / Beulah'],
  ['America', 'America/North_Dakota/Center', 'North Dakota / Center'],
  ['America', 'America/North_Dakota/New_Salem', 'North Dakota / New Salem'],
  ['America', 'America/Rainy_River', 'Rainy River'],
  ['America', 'America/Rankin_Inlet', 'Rankin Inlet'],
  ['America', 'America/Regina', 'Regina'],
  ['America', 'America/Resolute', 'Resolute'],
  ['America', 'America/Swift_Current', 'Swift Current'],
  ['America', 'America/Tegucigalpa', 'Tegucigalpa'],
  ['America', 'America/Winnipeg', 'Winnipeg'],
  ['America', 'America/Boise', 'Boise'],
  ['America', 'America/Cambridge_Bay', 'Cambridge Bay'],
  ['America', 'America/Chihuahua', 'Chihuahua'],
  ['America', 'America/Creston', 'Creston'],
  ['America', 'America/Dawson_Creek', 'Dawson Creek'],
  ['America', 'America/Denver', 'Denver'],
  ['America', 'America/Edmonton', 'Edmonton'],
  ['America', 'America/Fort_Nelson', 'Fort Nelson'],
  ['America', 'America/Hermosillo', 'Hermosillo'],
  ['America', 'America/Inuvik', 'Inuvik'],
  ['America', 'America/Mazatlan', 'Mazatlan'],
  ['America', 'America/Ojinaga', 'Ojinaga'],
  ['America', 'America/Phoenix', 'Phoenix'],
  ['America', 'America/Yellowknife', 'Yellowknife'],
  ['America', 'America/Dawson', 'Dawson'],
  ['America', 'America/Los_Angeles', 'Los Angeles'],
  ['America', 'America/Tijuana', 'Tijuana'],
  ['America', 'America/Vancouver', 'Vancouver'],
  ['America', 'America/Whitehorse', 'Whitehorse'],
  ['America', 'America/Anchorage', 'Anchorage'],
  ['America', 'America/Juneau', 'Juneau'],
  ['America', 'America/Metlakatla', 'Metlakatla'],
  ['America', 'America/Nome', 'Nome'],
  ['America', 'America/Sitka', 'Sitka'],
  ['America', 'America/Yakutat', 'Yakutat'],
  ['America', 'America/Adak', 'Adak'],

  ['Europe', 'Europe/Dublin', 'Dublin'],
  ['Europe', 'Europe/Guernsey', 'Guernsey'],
  ['Europe', 'Europe/Isle_of_Man', 'Isle of Man'],
  ['Europe', 'Europe/Jersey', 'Jersey'],
  ['Europe', 'Europe/Lisbon', 'Lisbon'],
  ['Europe', 'Europe/London', 'London'],
  ['Europe', 'Europe/Amsterdam', 'Amsterdam'],
  ['Europe', 'Europe/Andorra', 'Andorra'],
  ['Europe', 'Europe/Belgrade', 'Belgrade'],
  ['Europe', 'Europe/Berlin', 'Berlin'],
  ['Europe', 'Europe/Bratislava', 'Bratislava'],
  ['Europe', 'Europe/Brussels', 'Brussels'],
  ['Europe', 'Europe/Budapest', 'Budapest'],
  ['Europe', 'Europe/Busingen', 'Busingen'],
  ['Europe', 'Europe/Copenhagen', 'Copenhagen'],
  ['Europe', 'Europe/Gibraltar', 'Gibraltar'],
  ['Europe', 'Europe/Ljubljana', 'Ljubljana'],
  ['Europe', 'Europe/Luxembourg', 'Luxembourg'],
  ['Europe', 'Europe/Madrid', 'Madrid'],
  ['Europe', 'Europe/Malta', 'Malta'],
  ['Europe', 'Europe/Monaco', 'Monaco'],
  ['Europe', 'Europe/Oslo', 'Oslo'],
  ['Europe', 'Europe/Paris', 'Paris'],
  ['Europe', 'Europe/Podgorica', 'Podgorica'],
  ['Europe', 'Europe/Prague', 'Prague'],
  ['Europe', 'Europe/Rome', 'Rome'],
  ['Europe', 'Europe/San_Marino', 'San Marino'],
  ['Europe', 'Europe/Sarajevo', 'Sarajevo'],
  ['Europe', 'Europe/Skopje', 'Skopje'],
  ['Europe', 'Europe/Stockholm', 'Stockholm'],
  ['Europe', 'Europe/Tirane', 'Tirane'],
  ['Europe', 'Europe/Vaduz', 'Vaduz'],
  ['Europe', 'Europe/Vatican', 'Vatican'],
  ['Europe', 'Europe/Vienna', 'Vienna'],
  ['Europe', 'Europe/Warsaw', 'Warsaw'],
  ['Europe', 'Europe/Zagreb', 'Zagreb'],
  ['Europe', 'Europe/Zurich', 'Zurich'],
  ['Europe', 'Europe/Athens', 'Athens'],
  ['Europe', 'Europe/Bucharest', 'Bucharest'],
  ['Europe', 'Europe/Chisinau', 'Chisinau'],
  ['Europe', 'Europe/Helsinki', 'Helsinki'],
  ['Europe', 'Europe/Kaliningrad', 'Kaliningrad'],
  ['Europe', 'Europe/Mariehamn', 'Mariehamn'],
  ['Europe', 'Europe/Riga', 'Riga'],
  ['Europe', 'Europe/Sofia', 'Sofia'],
  ['Europe', 'Europe/Tallinn', 'Tallinn'],
  ['Europe', 'Europe/Uzhgorod', 'Uzhgorod'],
  ['Europe', 'Europe/Vilnius', 'Vilnius'],
  ['Europe', 'Europe/Zaporozhye', 'Zaporozhye'],
  ['Europe', 'Europe/Istanbul', 'Istanbul'],
  ['Europe', 'Europe/Kyiv', 'Kyiv'],
  ['Europe', 'Europe/Minsk', 'Minsk'],
  ['Europe', 'Europe/Moscow', 'Moscow'],
  ['Europe', 'Europe/Simferopol', 'Simferopol'],
  ['Europe', 'Europe/Samara', 'Samara'],
  ['Europe', 'Europe/Volgograd', 'Volgograd'],

  ['Asia', 'Asia/Amman', 'Amman'],
  ['Asia', 'Asia/Beirut', 'Beirut'],
  ['Asia', 'Asia/Damascus', 'Damascus'],
  ['Asia', 'Asia/Gaza', 'Gaza'],
  ['Asia', 'Asia/Hebron', 'Hebron'],
  ['Asia', 'Asia/Jerusalem', 'Jerusalem'],
  ['Asia', 'Asia/Nicosia', 'Nicosia'],
  ['Asia', 'Asia/Aden', 'Aden'],
  ['Asia', 'Asia/Baghdad', 'Baghdad'],
  ['Asia', 'Asia/Bahrain', 'Bahrain'],
  ['Asia', 'Asia/Kuwait', 'Kuwait'],
  ['Asia', 'Asia/Qatar', 'Qatar'],
  ['Asia', 'Asia/Riyadh', 'Riyadh'],
  ['Asia', 'Asia/Tehran', 'Tehran'],
  ['Asia', 'Asia/Baku', 'Baku'],
  ['Asia', 'Asia/Dubai', 'Dubai'],
  ['Asia', 'Asia/Muscat', 'Muscat'],
  ['Asia', 'Asia/Tbilisi', 'Tbilisi'],
  ['Asia', 'Asia/Yerevan', 'Yerevan'],
  ['Asia', 'Asia/Kabul', 'Kabul'],
  ['Asia', 'Asia/Aqtau', 'Aqtau'],
  ['Asia', 'Asia/Aqtobe', 'Aqtobe'],
  ['Asia', 'Asia/Ashgabat', 'Ashgabat'],
  ['Asia', 'Asia/Dushanbe', 'Dushanbe'],
  ['Asia', 'Asia/Karachi', 'Karachi'],
  ['Asia', 'Asia/Oral', 'Oral'],
  ['Asia', 'Asia/Samarkand', 'Samarkand'],
  ['Asia', 'Asia/Tashkent', 'Tashkent'],
  ['Asia', 'Asia/Yekaterinburg', 'Yekaterinburg'],
  ['Asia', 'Asia/Colombo', 'Colombo'],
  ['Asia', 'Asia/Kolkata', 'Kolkata'],
  ['Asia', 'Asia/Kathmandu', 'Kathmandu'],
  ['Asia', 'Asia/Almaty', 'Almaty'],
  ['Asia', 'Asia/Bishkek', 'Bishkek'],
  ['Asia', 'Asia/Dhaka', 'Dhaka'],
  ['Asia', 'Asia/Novosibirsk', 'Novosibirsk'],
  ['Asia', 'Asia/Omsk', 'Omsk'],
  ['Asia', 'Asia/Qyzylorda', 'Qyzylorda'],
  ['Asia', 'Asia/Thimphu', 'Thimphu'],
  ['Asia', 'Asia/Urumqi', 'Urumqi'],
  ['Asia', 'Asia/Rangoon', 'Rangoon'],
  ['Asia', 'Asia/Bangkok', 'Bangkok'],
  ['Asia', 'Asia/Ho_Chi_Minh', 'Ho Chi Minh'],
  ['Asia', 'Asia/Hovd', 'Hovd'],
  ['Asia', 'Asia/Jakarta', 'Jakarta'],
  ['Asia', 'Asia/Krasnoyarsk', 'Krasnoyarsk'],
  ['Asia', 'Asia/Novokuznetsk', 'Novokuznetsk'],
  ['Asia', 'Asia/Phnom_Penh', 'Phnom Penh'],
  ['Asia', 'Asia/Pontianak', 'Pontianak'],
  ['Asia', 'Asia/Vientiane', 'Vientiane'],
  ['Asia', 'Asia/Brunei', 'Brunei'],
  ['Asia', 'Asia/Choibalsan', 'Choibalsan'],
  ['Asia', 'Asia/Hong_Kong', 'Hong Kong'],
  ['Asia', 'Asia/Irkutsk', 'Irkutsk'],
  ['Asia', 'Asia/Kuala_Lumpur', 'Kuala Lumpur'],
  ['Asia', 'Asia/Kuching', 'Kuching'],
  ['Asia', 'Asia/Macau', 'Macau'],
  ['Asia', 'Asia/Makassar', 'Makassar'],
  ['Asia', 'Asia/Manila', 'Manila'],
  ['Asia', 'Asia/Shanghai', 'Shanghai'],
  ['Asia', 'Asia/Singapore', 'Singapore'],
  ['Asia', 'Asia/Taipei', 'Taipei'],
  ['Asia', 'Asia/Ulaanbaatar', 'Ulaanbaatar'],
  ['Asia', 'Asia/Chita', 'Chita'],
  ['Asia', 'Asia/Dili', 'Dili'],
  ['Asia', 'Asia/Jayapura', 'Jayapura'],
  ['Asia', 'Asia/Khandyga', 'Khandyga'],
  ['Asia', 'Asia/Pyongyang', 'Pyongyang'],
  ['Asia', 'Asia/Seoul', 'Seoul'],
  ['Asia', 'Asia/Tokyo', 'Tokyo'],
  ['Asia', 'Asia/Yakutsk', 'Yakutsk'],
  ['Asia', 'Asia/Magadan', 'Magadan'],
  ['Asia', 'Asia/Sakhalin', 'Sakhalin'],
  ['Asia', 'Asia/Ust-Nera', 'Ust-Nera'],
  ['Asia', 'Asia/Vladivostok', 'Vladivostok'],
  ['Asia', 'Asia/Srednekolymsk', 'Srednekolymsk'],
  ['Asia', 'Asia/Anadyr', 'Anadyr'],
  ['Asia', 'Asia/Kamchatka', 'Kamchatka'],

  ['Australia', 'Australia/Perth', 'Perth'],
  ['Australia', 'Australia/Eucla', 'Eucla'],
  ['Australia', 'Australia/Darwin', 'Darwin'],
  ['Australia', 'Australia/Brisbane', 'Brisbane'],
  ['Australia', 'Australia/Lindeman', 'Lindeman'],
  ['Australia', 'Australia/Adelaide', 'Adelaide'],
  ['Australia', 'Australia/Broken_Hill', 'Broken Hill'],
  ['Australia', 'Australia/Currie', 'Currie'],
  ['Australia', 'Australia/Hobart', 'Hobart'],
  ['Australia', 'Australia/Lord_Howe', 'Lord_Howe'],
  ['Australia', 'Australia/Melbourne', 'Melbourne'],
  ['Australia', 'Australia/Sydney', 'Sydney'],

  ['Indian', 'Indian/Antananarivo', 'Antananarivo'],
  ['Indian', 'Indian/Comoro', 'Comoro'],
  ['Indian', 'Indian/Mayotte', 'Mayotte'],
  ['Indian', 'Indian/Mahe', 'Mahe'],
  ['Indian', 'Indian/Mauritius', 'Mauritius'],
  ['Indian', 'Indian/Reunion', 'Reunion'],
  ['Indian', 'Indian/Kerguelen', 'Kerguelen'],
  ['Indian', 'Indian/Maldives', 'Maldives'],
  ['Indian', 'Indian/Chagos', 'Chagos'],
  ['Indian', 'Indian/Cocos', 'Cocos'],
  ['Indian', 'Indian/Christmas', 'Christmas'],

  ['Africa', 'Africa/Abidjan', 'Abidjan'],
  ['Africa', 'Africa/Accra', 'Accra'],
  ['Africa', 'Africa/Bamako', 'Bamako'],
  ['Africa', 'Africa/Banjul', 'Banjul'],
  ['Africa', 'Africa/Bissau', 'Bissau'],
  ['Africa', 'Africa/Casablanca', 'Casablanca'],
  ['Africa', 'Africa/Conakry', 'Conakry'],
  ['Africa', 'Africa/Dakar', 'Dakar'],
  ['Africa', 'Africa/El_Aaiun', 'El Aaiun'],
  ['Africa', 'Africa/Freetown', 'Freetown'],
  ['Africa', 'Africa/Lome', 'Lome'],
  ['Africa', 'Africa/Monrovia', 'Monrovia'],
  ['Africa', 'Africa/Nouakchott', 'Nouakchott'],
  ['Africa', 'Africa/Ouagadougou', 'Ouagadougou'],
  ['Africa', 'Africa/Sao_Tome', 'Sao Tome'],
  ['Africa', 'Africa/Algiers', 'Algiers'],
  ['Africa', 'Africa/Bangui', 'Bangui'],
  ['Africa', 'Africa/Brazzaville', 'Brazzaville'],
  ['Africa', 'Africa/Ceuta', 'Ceuta'],
  ['Africa', 'Africa/Douala', 'Douala'],
  ['Africa', 'Africa/Kinshasa', 'Kinshasa'],
  ['Africa', 'Africa/Lagos', 'Lagos'],
  ['Africa', 'Africa/Libreville', 'Libreville'],
  ['Africa', 'Africa/Luanda', 'Luanda'],
  ['Africa', 'Africa/Malabo', 'Malabo'],
  ['Africa', 'Africa/Ndjamena', 'Ndjamena'],
  ['Africa', 'Africa/Niamey', 'Niamey'],
  ['Africa', 'Africa/Porto-Novo', 'Porto-Novo'],
  ['Africa', 'Africa/Tunis', 'Tunis'],
  ['Africa', 'Africa/Blantyre', 'Blantyre'],
  ['Africa', 'Africa/Bujumbura', 'Bujumbura'],
  ['Africa', 'Africa/Cairo', 'Cairo'],
  ['Africa', 'Africa/Gaborone', 'Gaborone'],
  ['Africa', 'Africa/Harare', 'Harare'],
  ['Africa', 'Africa/Johannesburg', 'Johannesburg'],
  ['Africa', 'Africa/Juba', 'Juba'],
  ['Africa', 'Africa/Khartoum', 'Khartoum'],
  ['Africa', 'Africa/Kigali', 'Kigali'],
  ['Africa', 'Africa/Lubumbashi', 'Lubumbashi'],
  ['Africa', 'Africa/Lusaka', 'Lusaka'],
  ['Africa', 'Africa/Maputo', 'Maputo'],
  ['Africa', 'Africa/Maseru', 'Maseru'],
  ['Africa', 'Africa/Mbabane', 'Mbabane'],
  ['Africa', 'Africa/Tripoli', 'Tripoli'],
  ['Africa', 'Africa/Windhoek', 'Windhoek'],
  ['Africa', 'Africa/Addis_Ababa', 'Addis Ababa'],
  ['Africa', 'Africa/Asmara', 'Asmara'],
  ['Africa', 'Africa/Dar_es_Salaam', 'Dar es Salaam'],
  ['Africa', 'Africa/Djibouti', 'Djibouti'],
  ['Africa', 'Africa/Kampala', 'Kampala'],
  ['Africa', 'Africa/Mogadishu', 'Mogadishu'],
  ['Africa', 'Africa/Nairobi', 'Nairobi'],

  ['Pacific', 'Pacific/Palau', 'Palau'],
  ['Pacific', 'Pacific/Chuuk', 'Chuuk'],
  ['Pacific', 'Pacific/Guam', 'Guam'],
  ['Pacific', 'Pacific/Port_Moresby', 'Port Moresby'],
  ['Pacific', 'Pacific/Saipan', 'Saipan'],
  ['Pacific', 'Pacific/Bougainville', 'Bougainville'],
  ['Pacific', 'Pacific/Efate', 'Efate'],
  ['Pacific', 'Pacific/Guadalcanal', 'Guadalcanal'],
  ['Pacific', 'Pacific/Kosrae', 'Kosrae'],
  ['Pacific', 'Pacific/Norfolk', 'Norfolk'],
  ['Pacific', 'Pacific/Noumea', 'Noumea'],
  ['Pacific', 'Pacific/Pohnpei', 'Pohnpei'],
  ['Pacific', 'Pacific/Funafuti', 'Funafuti'],
  ['Pacific', 'Pacific/Kwajalein', 'Kwajalein'],
  ['Pacific', 'Pacific/Majuro', 'Majuro'],
  ['Pacific', 'Pacific/Nauru', 'Nauru'],
  ['Pacific', 'Pacific/Tarawa', 'Tarawa'],
  ['Pacific', 'Pacific/Wake', 'Wake'],
  ['Pacific', 'Pacific/Wallis', 'Wallis'],
  ['Pacific', 'Pacific/Auckland', 'Auckland'],
  ['Pacific', 'Pacific/Enderbury', 'Enderbury'],
  ['Pacific', 'Pacific/Fakaofo', 'Fakaofo'],
  ['Pacific', 'Pacific/Fiji', 'Fiji'],
  ['Pacific', 'Pacific/Tongatapu', 'Tongatapu'],
  ['Pacific', 'Pacific/Chatham', 'Chatham'],
  ['Pacific', 'Pacific/Apia', 'Apia'],
  ['Pacific', 'Pacific/Kiritimati', 'Kiritimati'],
  ['Pacific', 'Pacific/Easter', 'Easter'],
  ['Pacific', 'Pacific/Galapagos', 'Galapagos'],
  ['Pacific', 'Pacific/Pitcairn', 'Pitcairn'],
  ['Pacific', 'Pacific/Gambier', 'Gambier'],
  ['Pacific', 'Pacific/Marquesas', 'Marquesas'],
  ['Pacific', 'Pacific/Honolulu', 'Honolulu'],
  ['Pacific', 'Pacific/Johnston', 'Johnston'],
  ['Pacific', 'Pacific/Rarotonga', 'Rarotonga'],
  ['Pacific', 'Pacific/Tahiti', 'Tahiti'],
  ['Pacific', 'Pacific/Midway', 'Midway'],
  ['Pacific', 'Pacific/Niue', 'Niue'],
  ['Pacific', 'Pacific/Pago_Pago', 'Pago Pago'],

  ['Atlantic', 'Atlantic/Canary', 'Canary'],
  ['Atlantic', 'Atlantic/Faroe', 'Faroe'],
  ['Atlantic', 'Atlantic/Madeira', 'Madeira'],
  ['Atlantic', 'Atlantic/Reykjavik', 'Reykjavik'],
  ['Atlantic', 'Atlantic/St_Helena', 'St Helena'],
  ['Atlantic', 'Atlantic/Azores', 'Azores'],
  ['Atlantic', 'Atlantic/Cape_Verde', 'Cape Verde'],
  ['Atlantic', 'Atlantic/South_Georgia', 'South Georgia'],
  ['Atlantic', 'Atlantic/Stanley', 'Stanley'],
  ['Atlantic', 'Atlantic/Bermuda', 'Bermuda'],

  ['Antarctica', 'Antarctica/Troll', 'Troll'],
  ['Antarctica', 'Antarctica/Syowa', 'Syowa'],
  ['Antarctica', 'Antarctica/Mawson', 'Mawson'],
  ['Antarctica', 'Antarctica/Vostok', 'Vostok'],
  ['Antarctica', 'Antarctica/Davis', 'Davis'],
  ['Antarctica', 'Antarctica/Casey', 'Casey'],
  ['Antarctica', 'Antarctica/DumontDUrville', 'DumontDUrville'],
  ['Antarctica', 'Antarctica/Macquarie', 'Macquarie'],
  ['Antarctica', 'Antarctica/McMurdo', 'McMurdo'],
  ['Antarctica', 'Antarctica/Palmer', 'Palmer'],
  ['Antarctica', 'Antarctica/Rothera', 'Rothera'],
  ['Arctic', 'Arctic/Longyearbyen', 'Longyearbyen'],
];

const OffsetLabel = styled('div')`
  color: ${p => p.theme.subText};
  font-weight: ${p => p.theme.fontWeight.bold};
  display: flex;
  align-items: center;
  font-size: ${p => p.theme.fontSize.sm};
  width: max-content;
`;

const groupedTimezones = Object.entries(groupBy(timezones, ([group]) => group));

const timezoneOptions: Array<SelectValue<string>> = groupedTimezones.map(
  ([group, zones]) => ({
    value: '',
    label: group,
    options: zones.map(([_, value, label]) => {
      const offsetLabel = moment.tz(value).format('Z');
      return {
        value,
        trailingItems: <OffsetLabel>UTC {offsetLabel}</OffsetLabel>,
        label,
        textValue: `${group} ${label} ${offsetLabel}`,
      };
    }),
  })
);

export {timezoneOptions};
