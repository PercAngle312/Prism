"""Desktop equivalent of the native Indigo / Spice / Platinum RGB565 flow."""
def theme_rgb565(x,y):
    t=x*255//63
    orange=max(0,255-((x-17)**2+(y-47)**2)*255//1100)
    orange=orange*orange//255
    shade=min(100,max(0,(x+y-65)*2))
    rgb=[]
    for indigo,platinum,spice,black in zip((72,45,132),(169,174,182),(229,101,32),(20,22,27)):
        value=(indigo*(255-t)+platinum*t)//255
        value=(value*(255-orange)+spice*orange)//255
        value=(value*(255-shade)+black*shade)//255
        rgb.append(value*55//100)
    return (rgb[0]>>3)<<11 | (rgb[1]>>2)<<5 | rgb[2]>>3

def make_theme_image(size=(640,480)):
    from PIL import Image
    image=Image.new('RGB',(64,64))
    image.putdata([((p>>11)*255//31,((p>>5)&63)*255//63,(p&31)*255//31)
                   for y in range(64) for x in range(64) for p in [theme_rgb565(x,y)]])
    return image.resize(size,Image.Resampling.BILINEAR)
