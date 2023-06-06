from flask import Flask, render_template, request, redirect, url_for
import numpy as np
import pandas as pd
from src.backend.frontend_handler import foodfind_asap, foodfind_nearest
from datetime import datetime, timedelta
from shapely.geometry import Point
import re

MAP_CENTRE = [53.4, -1.4]
MAP_ZOOM = 11
PC_DATA = pd.read_csv("data/shef_pc_coords_lookup.csv")
PC_LIST = PC_DATA["postcode"].to_list()


def html_table(df):
    # Ranks, indexed from 1 for readability
    df_out = df.assign(rank=range(len(df)))
    df_out["rank"] = df_out["rank"] + 1

    # Handles missing contact details
    df_out = df_out.fillna("")

    # Reformat the contact links into one field, for compact display
    df_out['email'] = "Email: " + '<a href="mailto:' + df_out['email'] + '">' + df_out['email'] + '</a>'
    df_out['website'] = "Website: " + '<a href="' + "https://" +  df_out['website'] + '">' + df_out['website'] + "</a>"
    df_out['contact'] = df_out.apply(lambda row: "<br>".join([row['website'], row['email'], row['phone']]), axis=1)

    # Reformat address and postcode into one field, for compact display
    df_out['address'] = df_out['address'] + "<br>" + "<b>" + df_out['postcode'] + "</b>"

    # Mark metadata clearly
    df_out['referral_required'] = np.where(df['referral_required'], "Yes", "")
    df_out['delivery_option'] = np.where(df['delivery_option'], "Yes", "")
    
    # Format table column heads for readability
    df_out = df_out.rename(
        columns={"referral_required": "referral", "delivery_option": "delivery", "rank": "number"}
    )[
        [
            "number",
            "name",
            "address",
            "opening",
            "contact",
            "referral",
            "delivery"
        ]
    ]
    df_out.columns = [col.capitalize() for col in df_out.columns]
    df_out.to_csv("test.csv")

    return df_out.to_html(
        classes="table table-striped table-bordered table-sm table-hover",
        index=False,
        escape=False,
        render_links=True
    )


def get_coords_from_postcode(postcode):
    """ Helper, getting coordinate pair from postcode. """
    if postcode in PC_LIST:
        ind = PC_LIST.index(postcode)
        return [PC_DATA.lat[ind], PC_DATA.long[ind]]
    # If postcode not viable, return None
    else:
        return None


def get_coords_from_coords(coord_string):
    """ Helper, getting coordinates out of a coordinate string. """
    coords = re.search(
                r"LatLng\(([0-9\.-]+), ([0-9§.-]+)\)", coord_string  # noqa:W605
            )    
    if coords:
        gr = coords.groups()
        return [float(gr[0]), float(gr[1])]
    # If coordinate string not viable, return None
    else:
        return None


app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    # Handle case, no search
    if request.method == "GET":
        return render_template(
            "index.html",
            pc_list=PC_LIST,
            foodbanks="",
            df=pd.DataFrame(),
            map_centre=MAP_CENTRE,
            map_zoom=MAP_ZOOM,
            marker=MAP_CENTRE,
        )
    
    # Handle case, search posted
    if request.method == "POST":
        query_type = request.form["query_type"]
        query_location = request.form["query_location"]
        map_zoom = MAP_ZOOM

        if query_location == "postcode":
            postcode = request.form["pcode"]
            map_zoom = MAP_ZOOM + 2
            marker = get_coords_from_postcode(request.form["pcode"])
        
        elif query_location == "coords":
            map_zoom = MAP_ZOOM + 2
            marker = get_coords_from_coords(request.form["coords"])

        else:
            pass # For now, opportunity for better work here in future
        
        # Handle case, something wrong with location
        if not marker:
            return redirect(url_for("index"))

        range = float(request.form["range_val"])
        days = {
            x: (True if x in request.form.keys() else False)
            for x in [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
        }
        print(days)
        # query_backend( above parameters)
        if query_type == "nearest":
            if query_location == "postcode":
                foodbanks = foodfind_nearest(
                    method="postcode", postcode=postcode, dist_range=range * 1000, days=days
                )
            else:
                foodbanks = foodfind_nearest(
                    method="place_from",
                    place_from=Point(marker[1], marker[0]),
                    dist_range=range * 1000,
                    days=days,
                )
        else:
            if query_location == "postcode":
                foodbanks = foodfind_asap(
                    method="postcode", postcode=postcode, dist_range=range * 1000
                )
            else:
                foodbanks = foodfind_asap(
                    method="place_from", place_from=Point(marker[1], marker[0]), dist_range=range * 1000
                )

        foodbanks["color"] = "cyan"  # based on days to opening
        msk_today = foodbanks.opening.str.contains(datetime.now().strftime("%A"))
        msk_tomorrow = foodbanks.opening.str.contains(
            (datetime.now() + timedelta(days=1)).strftime("%A")
        )
        foodbanks.loc[msk_today | msk_tomorrow, "color"] = "blue"

        return render_template(
            "index.html",
            pc_list=PC_LIST,
            foodbanks=html_table(foodbanks),
            df=foodbanks,
            map_zoom=map_zoom,
            marker=marker,
        )        


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True)
