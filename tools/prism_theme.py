"""Desktop equivalent of the native Indigo / Spice / Platinum RGB565 flow."""
def theme_rgb565(x,y):
    t=(x*3+y*2)*255//315
    orange=max(0,255-abs(x+y-68)*255//42)
    orange=orange*orange//255
    shade=max(0,x+y-112)
    rgb=[]
    for indigo,platinum,spice,black in zip((92,60,172),(184,191,203),(240,126,50),(20,22,27)):
        value=(indigo*(255-t)+platinum*t)//255
        value=(value*(255-orange)+spice*orange)//255
        value=(value*(255-shade)+black*shade)//255
        rgb.append(value*82//100)
    return (rgb[0]>>3)<<11 | (rgb[1]>>2)<<5 | rgb[2]>>3

def make_theme_image(size=(640,480)):
    from PIL import Image
    image=Image.new('RGB',(64,64))
    image.putdata([((p>>11)*255//31,((p>>5)&63)*255//63,(p&31)*255//31)
                   for y in range(64) for x in range(64) for p in [theme_rgb565(x,y)]])
    return image.resize(size,Image.Resampling.BILINEAR)
